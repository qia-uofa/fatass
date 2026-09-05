"""Correctness: is the trial's response right, checked against a reference
answer carried on its own seed. Inherently binary — the value is always
exactly ``0.0`` or ``1.0``, never a genuine in-between."""

from __future__ import annotations

from .. import grading
from ..dataset import Trial
from .ground_truth import GroundTruth


class CorrectnessGT(GroundTruth):
    """Grades ``trial.response`` against ``trial.seed.answer`` (and, if the
    seed carries it, the seed's full ``aliases`` tuple — TriviaQA questions
    often have several accepted phrasings, and the paper's own grader is fed
    all of them, §2.3.1) via GPT-4o-mini (`vonto.grading.gpt4o_mini_grader`)
    when an OpenAI key is configured, exactly as the paper does. Without a
    key, falls back to asking the model under test itself
    (`vonto.grading.qwen_grader`) when constructed with a ``loaded`` model —
    a real semantic judgment call rather than string matching, though not an
    independent judge the way GPT-4o-mini or a human is. With no key and no
    ``loaded`` model, falls back further to `vonto.grading.alias_match_grader`
    (normalized substring containment), the only grading possible with
    neither — ``grader_used`` records which of the three actually ran,
    checked after ``values`` rather than printed unconditionally, since a GT
    has no notebook of its own to print into.

    Requires the seed type to actually carry an ``answer`` field (e.g.
    `TriviaQASeed`); raises loudly on a seed type that doesn't, rather than
    silently grading it wrong.
    """

    name = "correctness"
    tags = ["baseline", "general", "incorrect", "correct"]

    def __init__(self, loaded=None) -> None:
        self.loaded = loaded
        #: Set by `values()` to ``"gpt-4o-mini"``, ``"qwen"``, or
        #: ``"alias_match"`` — which grader actually ran on the most recent call.
        self.grader_used: str | None = None

    def values(self, trials: list[Trial]) -> list[float]:
        questions, answers, aliases = [], [], []
        for trial in trials:
            expected = getattr(trial.seed, "answer", None)
            if expected is None:
                raise ValueError(
                    f"{type(trial.seed).__name__} has no 'answer' field — CorrectnessGT "
                    "needs a reference answer to grade against"
                )
            questions.append(trial.inquiry.question)
            answers.append(trial.response)
            seed_aliases = getattr(trial.seed, "aliases", None)
            aliases.append(tuple(seed_aliases) if seed_aliases else (expected,))

        if grading.openai_available():
            grader, self.grader_used = grading.gpt4o_mini_grader, "gpt-4o-mini"
        elif self.loaded is not None:
            grader, self.grader_used = grading.qwen_grader, "qwen"
        else:
            grader, self.grader_used = grading.alias_match_grader, "alias_match"
        graded = grading.grade_answers(questions, answers, aliases, grader=grader, loaded=self.loaded)
        return [1.0 if correct else 0.0 for correct in graded]
