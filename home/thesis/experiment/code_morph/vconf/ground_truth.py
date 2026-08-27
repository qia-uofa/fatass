"""Ground truth for the reported sentiment (§2.3.1, §3.2).

Every experiment checks the model's self-report against *some* ground truth —
for the paper's own confidence/correctness pair, "is the answer factually
correct against these gold aliases." A ground truth is just that check, made
swappable: given the question and the model's own response, does the target
property hold?

The interface is informal (duck-typed, matching the rest of this package): an
object with a ``.label(item, trial) -> bool`` method and a batched
``.labels(items, trials) -> list[bool]``. Two implementations cover the two
shapes a ground truth naturally takes:

* :class:`AliasCorrectness` — compared against a *reference* (gold aliases),
  today's behavior, unchanged.
* :class:`LLMCriterion` — judged from the response *text alone*, for any
  ground truth that isn't a comparison against a reference answer. The
  question string passed to it is the parameter; no new code is needed per
  ground truth.

Ground truth stays boolean-only: :func:`vconf.metrics.expected_calibration_error`
and :func:`vconf.metrics.auroc` are calibration-against-a-binary-event
metrics, and generalizing them to a continuous ground truth is a separate,
larger change this module doesn't attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import config as cfg
from . import grading

if TYPE_CHECKING:
    from .data import QuestionItem
    from .pipeline import Trial


@dataclass
class AliasCorrectness:
    """Is the trial's answer factually correct against its gold aliases? (§2.3.1)

    Wraps the manual's own grader unchanged: GPT-4o-mini (temperature 0) when
    an OpenAI key is available, normalised alias matching (the documented,
    less reliable fallback) otherwise. All grades are cached to disk, exactly
    as :func:`vconf.grading.grade_answers` already does.
    """

    name: str = "correctness"
    grader: object = None
    cache_path: object = None  # defaults to cfg.GRADES_DIR / "grades.json", as today

    def label(self, item: "QuestionItem", trial: "Trial") -> bool:
        return self.labels([item], [trial])[0]

    def labels(self, items: list["QuestionItem"], trials: list["Trial"]) -> list[bool]:
        grader = self.grader or (
            grading.gpt4o_mini_grader if grading.openai_available() else grading.alias_match_grader
        )
        return grading.grade_answers(
            [t.question for t in trials],
            [t.answer for t in trials],
            [t.gold_answers for t in trials],
            grader=grader,
            cache_path=self.cache_path,
        )

    @property
    def grader_name(self) -> str:
        grader = self.grader or (
            grading.gpt4o_mini_grader if grading.openai_available() else grading.alias_match_grader
        )
        return getattr(grader, "__name__", str(grader))


@dataclass
class LLMCriterion:
    """A ground truth judged directly from the response text by GPT-4o-mini.

    ``question`` is a yes/no question about one trial's answer, e.g. "Does
    this response hedge its claim?" or "Is this answer overly formal?" — the
    ground truth *is* the answer to that question, not a comparison against a
    gold reference. Unlike :class:`AliasCorrectness`, this has no on-disk
    cache of its own; add one (mirroring :class:`vconf.grading.GradeCache`) if
    a real run needs to avoid repeated API calls across re-executions.
    """

    question: str
    name: str = "llm_criterion"
    client: object = None

    def label(self, item: "QuestionItem", trial: "Trial") -> bool:
        client = self.client or grading._client()
        response = client.chat.completions.create(
            model=cfg.GRADER_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": "Answer with exactly one word: YES or NO."},
                {
                    "role": "user",
                    "content": f"{self.question}\n\nText: {trial.answer}\n\nReply YES or NO.",
                },
            ],
        )
        return response.choices[0].message.content.strip().upper().startswith("YES")

    def labels(self, items: list["QuestionItem"], trials: list["Trial"]) -> list[bool]:
        return [self.label(item, trial) for item, trial in zip(items, trials)]
