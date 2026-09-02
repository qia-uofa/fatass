"""Answer grading and the hedging check (§2.3.1, §3.2).

TriviaQA free-text answers cannot be graded by string match reliably, so the
paper has **GPT-4o-mini** mark each question (model answer vs. gold aliases →
correct / incorrect) with a deterministic, temperature-0 single call returning a
bare ``CORRECT``/``INCORRECT`` token.  All grades are cached to disk and reused
across every experiment.

:func:`alias_match_grader` is the documented fallback used when no
``OPENAI_API_KEY`` is available: it is *not* what the paper used, and runs that
use it must say so.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import config as cfg

GRADER_SYSTEM_PROMPT = (
    "You mark short factual answers. Reply with exactly one word: CORRECT or INCORRECT."
)

GRADER_USER_TEMPLATE = (
    "Question: {question}\n"
    "Accepted answers: {aliases}\n"
    "Model answer: {answer}\n"
    "Is the model answer correct? Reply CORRECT or INCORRECT."
)

HEDGING_SYSTEM_PROMPT = (
    "You detect hedging language. Reply with exactly one word: YES or NO."
)

HEDGING_USER_TEMPLATE = (
    "Does this answer contain hedging language such as 'maybe', 'probably', "
    "'perhaps'?\nAnswer: {answer}\nReply YES or NO."
)


@dataclass
class GradeCache:
    """A JSON-backed cache of grades, keyed by a hash of the graded triple."""

    path: Path
    entries: dict[str, bool] = None

    def __post_init__(self):
        self.path = Path(self.path)
        if self.entries is None:
            self.entries = json.loads(self.path.read_text()) if self.path.exists() else {}

    @staticmethod
    def key(question: str, answer: str, aliases: tuple[str, ...]) -> str:
        blob = json.dumps([question, answer, sorted(aliases)], sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()

    def get(self, question: str, answer: str, aliases: tuple[str, ...]):
        return self.entries.get(self.key(question, answer, aliases))

    def put(self, question: str, answer: str, aliases: tuple[str, ...], value: bool) -> None:
        self.entries[self.key(question, answer, aliases)] = bool(value)

    def save(self) -> Path:
        """Write the cache atomically, so concurrent runs cannot read a half-written file."""
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
    """Fallback: normalised containment against the gold aliases.

    The manual explicitly warns this is unreliable for TriviaQA (§2.3.1); it
    exists so the pipeline can run without an OpenAI key, and any run that uses
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


def grade_answers(
    questions: list[str],
    answers: list[str],
    aliases: list[tuple[str, ...]],
    grader=None,
    cache_path: Path | None = None,
    client=None,
) -> list[bool]:
    """Grade every answer, caching to disk (§2.3.1 "cache all grades to disk")."""
    grader = grader or (gpt4o_mini_grader if openai_available() else alias_match_grader)
    cache = GradeCache(cache_path or (cfg.GRADES_DIR / "grades.json"))
    out: list[bool] = []
    for question, answer, alias in zip(questions, answers, aliases):
        cached = cache.get(question, answer, alias)
        if cached is None:
            kwargs = {"client": client} if grader is gpt4o_mini_grader else {}
            cached = bool(grader(question, answer, alias, **kwargs))
            cache.put(question, answer, alias, cached)
        out.append(cached)
    cache.save()
    return out


HEDGING_WORDS = ("maybe", "probably", "perhaps", "possibly", "i think", "not sure", "might be")


def keyword_hedging_check(answer: str) -> bool:
    """Fallback hedging detector used when no OpenAI key is available (§3.2)."""
    lowered = f" {answer.lower()} "
    return any(word in lowered for word in HEDGING_WORDS)


def gpt4o_mini_hedging_check(answer: str, client=None) -> bool:
    """GPT-4o-mini yes/no hedging classification, temperature 0 (§3.2)."""
    client = client or _client()
    response = client.chat.completions.create(
        model=cfg.GRADER_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": HEDGING_SYSTEM_PROMPT},
            {"role": "user", "content": HEDGING_USER_TEMPLATE.format(answer=answer)},
        ],
    )
    return response.choices[0].message.content.strip().upper().startswith("YES")


def hedging_rate(answers: list[str], checker=None, client=None) -> float:
    """Fraction of answers containing hedging language; the paper reports ~0% (§3.2)."""
    checker = checker or (gpt4o_mini_hedging_check if openai_available() else keyword_hedging_check)
    if not answers:
        return float("nan")
    flags = []
    for answer in answers:
        kwargs = {"client": client} if checker is gpt4o_mini_hedging_check else {}
        flags.append(bool(checker(answer, **kwargs)))
    return sum(flags) / len(flags)
