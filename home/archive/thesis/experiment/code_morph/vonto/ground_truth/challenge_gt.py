"""Challenge: the model's own resistance to changing its answer when shown
adversarial evidence, read straight off logits — computed counterpart to
`observation_method.ChallengeOM`'s self-report. Reproduces
`archive/vconf/commitment_challenge.py`'s protocol (dynamic evidence: genuine
if the model was wrong, a freshly generated counterfeit claim if it was
right — whichever actually argues against what the model currently
believes), simplified to just that generated-evidence condition (GEGT) — the
old hand-authored counterfeit tables (HEGT) are dropped rather than ported,
since they were per-dataset lookup tables keyed to a fixed, pre-existing item
set that has no equivalent here.

``compose_challenge_evidence`` is factored out (not inlined in `values`
below) so `observation_method.ChallengeOM`'s self-report can be shown the
*same* evidence this GT scores against, via `calibration.observation.
observe_trial`'s own special case for it — `ChallengeOM.criterion` asks "how
unwilling you are to changing your answer above if concrete evidence is
provided," but the generic self-report framing (`compose_self_report_inquiry`)
never actually shows any evidence, so without this the self-report and its
computed counterpart were conditioned on genuinely different situations. Both
the genuine (`generate_genuine_claim`) and counterfeit (`generate_counterfeit_
claim`) branches are themselves generated the same way (a fixed template
string for "genuine" would confound truth value with phrasing naturalness —
see `generate_genuine_claim`'s own docstring), and both sample at temperature
0.7 — so the disk cache, keyed by (question, response), is what guarantees
"same evidence" rather than "independently generated, probably-different
evidence" for the same trial, regardless of which branch fires."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from tqdm.auto import tqdm

from .. import config as cfg
from .. import grading
from ..dataset import Trial
from .ground_truth import GroundTruth

_CHALLENGE_QUESTION = 'Do you want to change your answer? Answer with only "Yes" or "No".'
#: Forced completion cue, same mechanism as `observation_method.LikertOM`
#: (reproduction guidebook §2.5.1's own technique, `archive/vconf`'s
#: ``RESPONSE_CUE``): appended *after* chat-templating so the model's turn is
#: prefilled starting mid-cue and the very next token is read at that exact
#: forced position — without it, the read position is the free-form start of
#: a fresh assistant turn, which the model is not guaranteed to answer
#: "Yes"/"No" at (it happens to comply often, but that's model good behavior,
#: not something this code enforces).
_ANSWER_CUE = "Answer:"


def _render_challenge_prompt(loaded, question: str, answer: str, evidence: str) -> str:
    body = f"Question: {question}\nAnswer: {answer}\n\n"
    if evidence:
        body += f"{evidence}\n\n"
    body += _CHALLENGE_QUESTION
    templated = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": body}], tokenize=False, add_generation_prompt=True
    )
    return templated + _ANSWER_CUE


def _generate_claim(loaded, prompt: str) -> str:
    import torch

    text = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
    )
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    with torch.no_grad():
        out = loaded.model.generate(
            **enc, max_new_tokens=40, do_sample=True, temperature=0.7,
            pad_token_id=loaded.tokenizer.pad_token_id,
        )
    new_tokens = out[:, enc["input_ids"].shape[1] :]
    return loaded.tokenizer.decode(new_tokens[0], skip_special_tokens=True).strip()


def generate_counterfeit_claim(loaded, question: str, correct_answer: str) -> str:
    """Ask the model itself for a specific, plausible-sounding wrong answer —
    used only when the model's own answer was actually correct, so no
    genuine adversarial evidence exists against it."""
    prompt = (
        f"Question: {question}\n"
        f"Write exactly one short, confident sentence claiming a specific answer to this "
        f"question that is DIFFERENT from '{correct_answer}' — write it as a sincere, "
        f"plausible-sounding claim, not a question or a hedge. Do not mention "
        f"'{correct_answer}' or acknowledge any uncertainty. Output only that one sentence.\n"
        f"Claim:"
    )
    return _generate_claim(loaded, prompt)


def generate_genuine_claim(loaded, question: str, correct_answer: str) -> str:
    """Ask the model itself to phrase the *genuine* evidence too, in the same
    style as `generate_counterfeit_claim` — one short, confident, sourced-
    sounding sentence — rather than a single fixed template string reused
    identically across every trial. A rigid canned sentence for "true" and
    freely generated prose for "false" would confound truth value with
    phrasing naturalness: the model could be reacting to how formulaic the
    claim sounds rather than to whether it's actually being challenged with
    something true or false. Both branches are now generated the same way,
    differing only in which answer they assert."""
    prompt = (
        f"Question: {question}\n"
        f"Write exactly one short, confident sentence, citing reliable sources, asserting "
        f"that the answer to this question is '{correct_answer}' — write it as a sincere, "
        f"plausible-sounding claim, not a question or a hedge. Output only that one sentence.\n"
        f"Claim:"
    )
    return _generate_claim(loaded, prompt)


@dataclass
class _EvidenceCache:
    """Disk-backed cache of composed evidence strings, keyed by (question,
    response) — same shape/atomic-save convention as `grading.GradeCache`,
    just string-valued instead of bool-valued."""

    path: Path
    entries: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            self.entries = json.loads(self.path.read_text())

    @staticmethod
    def key(question: str, response: str) -> str:
        blob = json.dumps([question, response], sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()

    def get(self, question: str, response: str) -> str | None:
        return self.entries.get(self.key(question, response))

    def put(self, question: str, response: str, evidence: str) -> None:
        self.entries[self.key(question, response)] = evidence

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(self.entries, indent=0))
        os.replace(temporary, self.path)
        return self.path


def compose_challenge_evidence(loaded, trial: Trial) -> str:
    """The adversarial evidence against ``trial``'s own answer — a generated
    genuine claim if it was wrong, a generated counterfeit claim if it was
    right (dynamic-evidence protocol, see module docstring); both generated
    the same way, differing only in truth value (see `generate_genuine_claim`).
    Cached to ``cfg.GRADES_DIR/challenge_evidence.json`` (grading-adjacent,
    same home `grading.GradeCache` uses) so every caller for the same trial
    gets back the exact same evidence, not just a similarly-generated one —
    both generation paths sample at temperature 0.7, so without this cache
    two independent calls for the same trial could disagree.
    """
    expected = getattr(trial.seed, "answer", None)
    if expected is None:
        raise ValueError(
            f"{type(trial.seed).__name__} has no 'answer' field — challenge evidence "
            "needs a reference answer to build against"
        )
    question = trial.inquiry.question
    aliases = getattr(trial.seed, "aliases", None) or (expected,)

    cache = _EvidenceCache(cfg.GRADES_DIR / "challenge_evidence.json")
    cached = cache.get(question, trial.response)
    if cached is not None:
        return cached

    answered_correctly = grading.alias_match_grader(question, trial.response, aliases)
    if answered_correctly:
        evidence = generate_counterfeit_claim(loaded, question, expected)
    else:
        evidence = generate_genuine_claim(loaded, question, expected)
    cache.put(question, trial.response, evidence)
    cache.save()
    return evidence


def _yes_no_margin(loaded, prompt: str) -> float:
    import torch

    enc = loaded.tokenizer([prompt], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    yes_id = loaded.tokenizer(" Yes", add_special_tokens=False)["input_ids"][0]
    no_id = loaded.tokenizer(" No", add_special_tokens=False)["input_ids"][0]
    with torch.no_grad():
        logits = loaded.model(**enc).logits[0, -1]
    return float(logits[no_id] - logits[yes_id])


class ChallengeGT(GroundTruth):
    """Needs a loaded model (bound at construction, not a bare module-level
    constant) — both generating the counterfeit claim and reading the Yes/No
    margin are real forward passes. Absolute per trial: whichever evidence
    argues against *this* trial's own answer (genuine, if it was wrong; a
    freshly generated counterfeit claim, if it was right — see
    `_model_answered_correctly`-equivalent check below) is presented, and the
    score is the logit-margin drop (baseline defend-margin minus challenged
    defend-margin), squashed through a sigmoid into ``[0, 1]`` — higher means
    more resistant (kept defending "No" even once challenged), matching
    `observation_method.ChallengeOM`'s own low-to-high direction.
    """

    name = "challenge"
    tags = ["baseline", "general", "caves", "defends"]

    def __init__(self, loaded) -> None:
        self.loaded = loaded

    def values(self, trials: list[Trial]) -> list[float]:
        out = []
        for trial in tqdm(trials, desc="challenge: baseline vs. challenged margins", leave=False):
            evidence = compose_challenge_evidence(self.loaded, trial)
            question = trial.inquiry.question
            baseline_margin = _yes_no_margin(
                self.loaded, _render_challenge_prompt(self.loaded, question, trial.response, "")
            )
            challenged_margin = _yes_no_margin(
                self.loaded, _render_challenge_prompt(self.loaded, question, trial.response, evidence)
            )
            drop = baseline_margin - challenged_margin
            out.append(1.0 / (1.0 + math.exp(-drop)))
        return out
