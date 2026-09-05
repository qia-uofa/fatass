"""Answer grading (reproduction guidebook §2.3.1): TriviaQA free-text answers
cannot be graded by string match reliably, so the paper has **GPT-4o-mini**
mark each question (model answer vs. gold aliases -> correct/incorrect) with
a deterministic, temperature-0 single call returning a bare
``CORRECT``/``INCORRECT`` token. All grades are cached to disk and reused
across every run.

``alias_match_grader`` is the documented fallback used when no
``OPENAI_API_KEY`` is available: it is *not* what the paper used, and
`ground_truth.CorrectnessGT` reports which one actually graded a given run
rather than presenting either silently as the other.

``qwen_grader`` is a second fallback, one step above alias matching: the same
``CORRECT``/``INCORRECT`` judgment, asked of the model under test itself
(greedy, temperature 0) instead of an external API — no key needed, and a
semantic judgment call rather than normalized substring containment, at the
cost of asking the model to grade its own answer rather than an independent
judge.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config as cfg

GRADER_SYSTEM_PROMPT = "You mark short factual answers. Reply with exactly one word: CORRECT or INCORRECT."

GRADER_USER_TEMPLATE = (
    "Question: {question}\n"
    "Accepted answers: {aliases}\n"
    "Model answer: {answer}\n"
    "Is the model answer correct? Reply CORRECT or INCORRECT."
)


@dataclass
class GradeCache:
    """A JSON-backed cache of grades, keyed by a hash of the graded triple."""

    path: Path
    entries: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            self.entries = json.loads(self.path.read_text())

    @staticmethod
    def key(grader_name: str, question: str, answer: str, aliases: tuple[str, ...]) -> str:
        # `grader_name` is part of the hash so switching graders (e.g.
        # alias_match -> qwen_grader once a model is available) can't
        # silently serve a grade cached under a different method's judgment.
        blob = json.dumps([grader_name, question, answer, sorted(aliases)], sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()

    def get(self, grader_name: str, question: str, answer: str, aliases: tuple[str, ...]):
        return self.entries.get(self.key(grader_name, question, answer, aliases))

    def put(self, grader_name: str, question: str, answer: str, aliases: tuple[str, ...], value: bool) -> None:
        self.entries[self.key(grader_name, question, answer, aliases)] = bool(value)

    def save(self) -> Path:
        """Write the cache atomically, so a concurrent run can't read a half-written file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(self.entries, indent=0))
        os.replace(temporary, self.path)
        return self.path


def normalize_answer(text: str) -> str:
    """Lower-case, strip articles/punctuation — used by the fallback grader only."""
    text = text.lower().strip()
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def alias_match_grader(question: str, answer: str, aliases: tuple[str, ...]) -> bool:
    """Fallback: normalized containment against the gold aliases.

    The guidebook explicitly warns this is unreliable for TriviaQA (§2.3.1);
    it exists so grading can run without an OpenAI key, and any run that uses
    it must report that its correctness labels are not the paper's.
    """
    norm_answer = normalize_answer(answer)
    if not norm_answer:
        return False
    for alias in aliases:
        norm_alias = normalize_answer(alias)
        if not norm_alias:
            continue
        if norm_answer == norm_alias or norm_alias in norm_answer or norm_answer in norm_alias:
            return True
    return False


def openai_available() -> bool:
    cfg.load_credentials()
    return bool(os.environ.get("OPENAI_API_KEY"))


def _client():
    from openai import OpenAI

    cfg.load_credentials()
    return OpenAI()


def gpt4o_mini_grader(question: str, answer: str, aliases: tuple[str, ...], client=None) -> bool:
    """One deterministic GPT-4o-mini call returning CORRECT / INCORRECT (§2.3.1)."""
    client = client or _client()
    response = client.chat.completions.create(
        model=cfg.GRADER_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": GRADER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": GRADER_USER_TEMPLATE.format(
                    question=question, aliases="; ".join(aliases), answer=answer
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip().upper().startswith("CORRECT")


def qwen_grader(question: str, answer: str, aliases: tuple[str, ...], loaded=None) -> bool:
    """One deterministic local-model call returning CORRECT / INCORRECT — the
    same criterion and prompt `gpt4o_mini_grader` uses (§2.3.1), asked of the
    model under test itself instead of an external API. Greedy (temperature
    0); more than a couple of tokens are generated (not a single forced one,
    and not just enough for the verdict word alone) since, unlike the Likert
    self-reports, "CORRECT"/"INCORRECT" aren't engineered to diverge at their
    very first token on every tokenizer, *and* — unlike GPT-4o-mini, which
    reliably complies with "reply with exactly one word" — a 7B instruct
    model is more likely to prepend a token or two ("Answer:", a leading
    filler word) before the verdict. A strict ``startswith`` check would
    silently read that as "not CORRECT" regardless of what the model actually
    said; checking for either word *anywhere* in the generated text is
    tolerant of that without needing to assume perfect compliance. Check
    INCORRECT first — it's not just "not CORRECT", it *contains* "CORRECT" as
    a substring, so checking CORRECT first would misread every INCORRECT as
    correct.
    """
    import torch

    prompt = GRADER_USER_TEMPLATE.format(question=question, aliases="; ".join(aliases), answer=answer)
    text = loaded.tokenizer.apply_chat_template(
        [
            {"role": "system", "content": GRADER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        tokenize=False, add_generation_prompt=True,
    )
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    with torch.no_grad():
        out = loaded.model.generate(
            **enc, max_new_tokens=10, do_sample=False, temperature=None, top_p=None, top_k=None,
            pad_token_id=loaded.tokenizer.pad_token_id,
        )
    new_tokens = out[:, enc["input_ids"].shape[1] :]
    response = loaded.tokenizer.decode(new_tokens[0], skip_special_tokens=True).strip().upper()
    if "INCORRECT" in response:
        return False
    return "CORRECT" in response


def grade_answers(
    questions: list[str],
    answers: list[str],
    aliases: list[tuple[str, ...]],
    grader=None,
    cache_path: Path | None = None,
    client=None,
    loaded=None,
) -> list[bool]:
    """Grade every answer, caching to disk (§2.3.1 "cache all grades to disk")."""
    grader = grader or (gpt4o_mini_grader if openai_available() else alias_match_grader)
    cache = GradeCache(cache_path or (cfg.GRADES_DIR / "grades.json"))
    out: list[bool] = []
    for question, answer, alias in zip(questions, answers, aliases):
        cached = cache.get(grader.__name__, question, answer, alias)
        if cached is None:
            if grader is gpt4o_mini_grader:
                kwargs = {"client": client}
            elif grader is qwen_grader:
                kwargs = {"loaded": loaded}
            else:
                kwargs = {}
            cached = bool(grader(question, answer, alias, **kwargs))
            cache.put(grader.__name__, question, answer, alias, cached)
        out.append(cached)
    cache.save()
    return out
