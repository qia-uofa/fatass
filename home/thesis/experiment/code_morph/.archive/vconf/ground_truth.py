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

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from . import config as cfg
from . import grading
from .metrics import mean_answer_logprob

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


# --------------------------------------------------------------------------- #
# Intrinsic ground truth — checked against the model's own generation, not an
# external fact (plan_benzon.md). Every ground truth above answers "was the
# self-report right, checked against something outside the model"; this one
# answers "is the self-report internally consistent with a quantity computed
# from the very forward pass/generation the self-report is about."
# --------------------------------------------------------------------------- #


def detect_yes_no_polarity(text: str) -> bool | None:
    """Best-effort yes/no polarity of a free-text answer, or ``None`` if unclear.

    Deliberately conservative: a hedged or non-committal answer ("it depends",
    "sort of", "technically...") returns ``None`` rather than guessing, so a
    caller can drop the trial instead of silently grading a hedge as wrong.
    Same lightweight keyword-matching spirit as :func:`grading.alias_match_grader`.
    """
    stripped = text.strip().lower()
    if not stripped:
        return None
    first_word = stripped.split()[0].strip(",.:;!\"'")
    if first_word in ("yes", "yeah", "yep", "true", "correct"):
        return True
    if first_word in ("no", "nope", "false", "incorrect"):
        return False
    hedges = (
        "it depends", "sort of", "kind of", "in a sense", "not exactly",
        "not quite", "technically", "somewhat", "arguably", "debatable",
    )
    if any(h in stripped for h in hedges):
        return None
    negatives = ("cannot", "can't", "isn't", "is not", "are not", "aren't", "doesn't", "does not")
    if any(p in stripped for p in negatives):
        return False
    positives = ("can ", "is able to", "is a ", "is an ", "are able to")
    if any(p in stripped for p in positives):
        return True
    return None


@dataclass
class IntrinsicMetricThreshold:
    """Ground truth computed from the model's own generation, not an external fact.

    ``metric_fn(trial)`` returns some quantity intrinsic to the trial itself
    (mean answer log-probability, output entropy, ...). The label is "this
    trial falls in the high half of the metric, within this run's own trial
    pool" — a median split over ``trials``, not an absolute threshold, since
    e.g. "high logprob" only means something relative to the same
    model/prompt/dataset's own distribution of logprobs. A trial whose metric
    is NaN (e.g. an empty answer) is always labeled ``False`` and excluded
    from the median computation itself.

    Deliberately pool-relative: :meth:`label` raises rather than guessing,
    since there is no meaningful "high" or "low" for a single trial seen in
    isolation. See ``plan_benzon.md``'s "pool-relative grading" wrinkle for
    why every call site must grade the full pool exactly once (in Exp0) and
    reuse that label thereafter, never recomputing it for one intervened
    trial.
    """

    name: str
    metric_fn: Callable[["Trial"], float]
    direction: str = "high"  # "high": True above the pool median; "low": True below

    def labels(self, items: list["QuestionItem"], trials: list["Trial"]) -> list[bool]:
        values = [self.metric_fn(t) for t in trials]
        finite = [v for v in values if v == v]  # NaN != NaN
        if not finite:
            return [False] * len(values)
        median = statistics.median(finite)
        if self.direction == "high":
            return [(v >= median) if v == v else False for v in values]
        return [(v <= median) if v == v else False for v in values]

    def label(self, item: "QuestionItem", trial: "Trial") -> bool:
        raise NotImplementedError(
            "IntrinsicMetricThreshold is pool-relative — call .labels() on the "
            "full trial set, never .label() on one trial in isolation."
        )


#: `sentiment.MACHINE_COMMITMENT`'s ground truth (plan_benzon.md Part 1,
#: revised) — nearly free, since `Trial.answer_logprobs` is already populated
#: for every trial regardless of dataset. `sentiment.NATURAL_COMMITMENT`'s
#: ground truth (the `commitment_challenge` adversarial-pressure threshold)
#: has no equivalent bare constant here — it needs a loaded model to run the
#: challenge battery, so it's built as a template via `functools.partial` at
#: the point a run's `RunConfig` actually exists (wrinkle #2 below), exactly
#: like `nuance`'s `metrics.answer_set_entropy`.
MACHINE_COMMITMENT_GROUND_TRUTH = IntrinsicMetricThreshold(
    name="answer_logprob", metric_fn=mean_answer_logprob
)


@dataclass
class OntologyTrivialAnswerKey:
    """Correctness for `benzon_data.load_ontology_trivials` (plan_benzon.md Part 2).

    Each item's expected yes/no answer is fixed at construction time
    (``item.meta["expected_answer"]``) — no external grader needed, just a
    polarity match on the Phase-0 answer via :func:`detect_yes_no_polarity`.
    An unparseable (hedged) answer is *not* silently graded wrong: it marks
    the trial invalid instead, mirroring `run_phase0`'s own empty-answer
    handling (``pipeline.py:212-214``), so `pipeline.filter_valid` drops it
    before analysis rather than it counting as a confident miss. Structurally
    identical to `SynonymAnswerKey` (plan_benzon.md Part 3), reused unchanged.
    """

    name: str = "ontology_trivial_answer_key"

    def label(self, item: "QuestionItem", trial: "Trial") -> bool:
        return self.labels([item], [trial])[0]

    def labels(self, items: list["QuestionItem"], trials: list["Trial"]) -> list[bool]:
        out: list[bool] = []
        for item, trial in zip(items, trials):
            polarity = detect_yes_no_polarity(trial.answer)
            if polarity is None:
                trial.valid = False
                trial.note = "unparseable polarity"
                out.append(False)  # never read — filter_valid drops this trial
                continue
            out.append(polarity == item.meta["expected_answer"])
        return out


def wordnet_category_membership(item_text: str, synset_name: str) -> bool | None:
    """Is ``item_text``'s most common noun sense the named WordNet synset, or
    one of its hyponyms?

    ``None`` if ``item_text``'s head noun (its last word — same convention as
    `benzon_data._wordnet_synonym_pairs`) has no WordNet noun sense at all —
    an "unparseable," not a confident negative (plan_benzon.md wrinkle 3,
    same convention as `detect_yes_no_polarity`): a made-up or wildly
    informal item shouldn't silently grade as "not a member" just because
    WordNet doesn't know the word.
    """
    import nltk

    try:
        from nltk.corpus import wordnet as wn

        wn.synsets("test")
    except LookupError:
        nltk.download("wordnet", quiet=True)
        from nltk.corpus import wordnet as wn

    head = item_text.strip().split()[-1].lower().rstrip(".,;:!?")
    synsets = wn.synsets(head, pos=wn.NOUN)
    if not synsets:
        return None
    target = wn.synset(synset_name)
    return any(s == target or target in s.closure(lambda node: node.hypernyms()) for s in synsets)


@dataclass
class ListItemCategoryMembership:
    """Correctness for one list-elicitation item's claimed category
    membership (plan_benzon.md Part 4): did the model's generated example
    genuinely belong to the category it was asked for?

    Checked externally, via WordNet hypernymy — legitimate here (unlike Part
    1's original commitment/nuance mistake, `plan_benzon.md`'s design note)
    because what's being checked is the model's own *generated choice* (did
    it pick a genuine example, or a borderline/wrong one — e.g. listing a
    whale under "fish"?), not a fact about a pre-selected question target
    that would need the answer known before generation — the claim under
    test only exists because the model made it.

    ``item.meta["synset"]`` names the WordNet synset the category maps to
    (`benzon_data.LIST_ELICITATION_CATEGORIES`); ``trial.answer`` is one
    *parsed* list item (`prompts.parse_list_items`), not the whole generated
    list — the caller builds one synthetic ``QuestionItem``/``Trial`` pair
    per item, mirroring `OntologyTrivialAnswerKey`'s per-trial shape.
    """

    name: str = "list_item_category_membership"

    def label(self, item: "QuestionItem", trial: "Trial") -> bool:
        return self.labels([item], [trial])[0]

    def labels(self, items: list["QuestionItem"], trials: list["Trial"]) -> list[bool]:
        out: list[bool] = []
        for item, trial in zip(items, trials):
            membership = wordnet_category_membership(trial.answer, item.meta["synset"])
            if membership is None:
                trial.valid = False
                trial.note = "item has no WordNet noun sense"
                out.append(False)  # never read — filter_valid drops this trial
                continue
            out.append(membership)
        return out


@dataclass
class SynonymAnswerKey(OntologyTrivialAnswerKey):
    """Correctness for `benzon_data.load_synonym_pairs` (plan_benzon.md Part 3).

    Identical mechanism to `OntologyTrivialAnswerKey` — subclassed rather than
    duplicated, since nothing in the base class is ontology-specific: both
    just check `detect_yes_no_polarity` against a fixed
    `item.meta["expected_answer"]` set at construction time (here, already
    accounting for `SYNONYM_TEMPLATES`' negation template flipping the
    expected polarity).
    """

    name: str = "synonym_answer_key"
