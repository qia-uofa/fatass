"""Parameterizing *what verbally-reported property* the pipeline studies (§2.5.1).

The two-phase protocol, the intervention battery and the metrics never need to
know the reported trait is "confidence" — they only ever read a ten-class
Likert scale and its prompt wording through a :class:`SentimentSpec`.
:data:`CONFIDENCE` reproduces the manual's own instance character-for-
character; any other sentiment is just another instance of the same
dataclass, built with a different name, criterion and class vocabulary.

Deliberately out of scope: the structural prompt markers a trial is parsed
against — ``**Confidence**:``, ``**Answer**:`` (:mod:`vconf.prompts`) — stay
fixed for every sentiment. Those mark *where* the self-report token sits in
the prompt, which every position-finding and intervention experiment depends
on; *what the self-report means* is what varies, and that's entirely carried
by the instruction prose built from a ``SentimentSpec``, not by the marker
text itself.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SentimentSpec:
    """One verbally-reported property, elicited as a ten-class Likert scale.

    ``classes`` is ordered low -> high; ``class_ranges`` gives each class's
    ``[lo, hi)`` share of the ``[0, 1]`` scale (used for the midpoint and the
    ECE binning). ``criterion`` is the clause completing "based on ..." in the
    classification instructions, and ``probability_clause`` completes "each
    category reflects the probability that ...". ``lead_in``, when given,
    replaces the whole generic "Classify your {name} into one of the
    following classes based on {criterion}" opening line of the categorical
    instructions (:func:`vconf.prompts._generic_categorical_instructions`)
    with a literal sentence of its own — for a sentiment whose natural
    phrasing isn't a bare classification (e.g. asking a direct question
    instead), while every other structural piece of the prompt (the class
    list, the probability-clause sentence, the ``**Confidence**:`` cue) stays
    exactly as generic. ``None`` (the default) keeps the fully generic
    wording, unchanged for every existing sentiment.
    """

    name: str
    criterion: str
    probability_clause: str
    classes: tuple[str, ...]
    class_ranges: dict[str, tuple[float, float]]
    high_band: tuple[str, ...]
    low_band: tuple[str, ...]
    highest_class: str
    lowest_class: str
    lead_in: str | None = None

    @property
    def class_midpoint(self) -> dict[str, float]:
        return {name: round((lo + hi) / 2, 2) for name, (lo, hi) in self.class_ranges.items()}

    @property
    def midpoints(self) -> np.ndarray:
        mid = self.class_midpoint
        return np.array([mid[name] for name in self.classes], dtype=float)


CONFIDENCE = SentimentSpec(
    name="confidence",
    criterion="how\nlikely the answer above is to be correct",
    probability_clause="the answer is correct",
    classes=(
        "No chance",
        "Really unlikely",
        "Chances are slight",
        "Unlikely",
        "Less than even",
        "Better than even",
        "Likely",
        "Very good chance",
        "Highly likely",
        "Almost certain",
    ),
    class_ranges={
        "No chance": (0.0, 0.1),
        "Really unlikely": (0.1, 0.2),
        "Chances are slight": (0.2, 0.3),
        "Unlikely": (0.3, 0.4),
        "Less than even": (0.4, 0.5),
        "Better than even": (0.5, 0.6),
        "Likely": (0.6, 0.7),
        "Very good chance": (0.7, 0.8),
        "Highly likely": (0.8, 0.9),
        "Almost certain": (0.9, 1.0),
    },
    high_band=("Very good chance", "Highly likely", "Almost certain"),
    low_band=("No chance", "Really unlikely", "Chances are slight"),
    highest_class="Almost certain",
    lowest_class="No chance",
)

#: "Commitment" splits into two sentiments, not one — `plan_benzon_implementation.md`
#: Phase 1 found that a single self-report correlated well with one candidate
#: ground truth (mean answer log-probability) and poorly with another
#: (`commitment_challenge`'s adversarial-pressure threshold), because those
#: two ground truths are different *constructs*, not two measurements of the
#: same thing: log-probability asks "how likely am I to give this same answer
#: again" (a machine-native self-consistency notion); the challenge protocol
#: asks "how hard would it be to talk me out of this" (the everyday human
#: notion of commitment). Splitting the self-report the same way lets each
#: one be checked against the ground truth it actually claims to track,
#: instead of one self-report being silently graded against whichever
#: ground truth the notebook happened to pick.

#: Unified commitment/resistance ladder shared by every commitment sentiment
#: below (`MACHINE_COMMITMENT`, `MACHINE_COMMITMENT_PARALLEL`,
#: `MACHINE_COMMITMENT_DEFINED`, `NATURAL_COMMITMENT`) — previously two
#: differently-worded 4-level ladders ("Barely/Somewhat/Mostly/Fully
#: committed" vs. "Readily/Somewhat/Rarely persuadable"/"Unpersuadable"),
#: unified into one shared vocabulary now that all four are compared side by
#: side in the same table (`notebooks_benzon/phase_0_calibration/1_commitment.ipynb`), and
#: widened from 4 to 8 levels for finer-grained measurement — the 4-level
#: scale was prone to collapsing entirely into the top class on some
#: datasets (e.g. `benzon:ontology_trivials`), leaving zero variance to
#: correlate against any ground truth. Distinct leading *words* per class
#: (§2.5.1, `test_every_defined_sentiments_classes_have_distinct_first_words`):
#: classification reads the model's logit at the first *token* of each class
#: name (`models.class_token_ids`), and a shared leading word is the easiest
#: way to accidentally collide on a shared first token too.
_COMMITMENT_CLASSES: tuple[str, ...] = (
    "Not committed",
    "Barely committed",
    "Slightly committed",
    "Somewhat committed",
    "Moderately committed",
    "Mostly committed",
    "Highly committed",
    "Fully committed",
)
_COMMITMENT_CLASS_RANGES: dict[str, tuple[float, float]] = {
    "Not committed": (0.0, 0.125),
    "Barely committed": (0.125, 0.25),
    "Slightly committed": (0.25, 0.375),
    "Somewhat committed": (0.375, 0.5),
    "Moderately committed": (0.5, 0.625),
    "Mostly committed": (0.625, 0.75),
    "Highly committed": (0.75, 0.875),
    "Fully committed": (0.875, 1.0),
}
#: Top/bottom two classes (25% of the scale each), matching the original
#: 4-level ladders' single-class (25%-wide) bands.
_COMMITMENT_HIGH_BAND: tuple[str, ...] = ("Highly committed", "Fully committed")
_COMMITMENT_LOW_BAND: tuple[str, ...] = ("Not committed", "Barely committed")

#: Self-consistency ("how committed are you to your answer"). Ground truth:
#: the model's own mean answer log-probability,
#: `ground_truth.MACHINE_COMMITMENT_GROUND_TRUTH`.
MACHINE_COMMITMENT = SentimentSpec(
    name="commitment level",
    criterion="how committed you are to the answer above",
    probability_clause="you would give the same answer again if asked",
    classes=_COMMITMENT_CLASSES,
    class_ranges=_COMMITMENT_CLASS_RANGES,
    high_band=_COMMITMENT_HIGH_BAND,
    low_band=_COMMITMENT_LOW_BAND,
    highest_class="Fully committed",
    lowest_class="Not committed",
)

#: A/B variant of `MACHINE_COMMITMENT`'s follow-up question: the same
#: self-consistency notion stated as a vivid "parallel timeline" scenario
#: instead of using the word "committed" at all — testing whether spelling
#: out *why* the question is about self-consistency changes how well the
#: self-report tracks the logprob ground truth. Same classes as
#: `MACHINE_COMMITMENT` (directly comparable output scale); only the
#: question differs.
MACHINE_COMMITMENT_PARALLEL = SentimentSpec(
    name="commitment level",
    criterion=(
        "if, in a parallel timeline, you were asked this exact same question again "
        "under the exact same conditions, how likely you would be to give the same answer"
    ),
    probability_clause="you would give the same answer again if asked",
    classes=_COMMITMENT_CLASSES,
    class_ranges=_COMMITMENT_CLASS_RANGES,
    high_band=_COMMITMENT_HIGH_BAND,
    low_band=_COMMITMENT_LOW_BAND,
    highest_class="Fully committed",
    lowest_class="Not committed",
)

#: Definition-augmented variant of `MACHINE_COMMITMENT`, same pattern as
#: `NUANCE_DEFINED` for `NUANCE`: identical criterion, prefixed with an
#: explicit dictionary definition of "commitment" — tests whether the bare
#: word reliably evokes self-consistency for the model, or whether spelling
#: out the sense intended changes how well the self-report tracks the logit
#: ground truth. Same classes as `MACHINE_COMMITMENT` (directly comparable
#: output scale); only the question differs.
MACHINE_COMMITMENT_DEFINED = SentimentSpec(
    name="commitment level",
    criterion=(
        '"Commitment" means: the state of being dedicated to a course of action, opinion, '
        "or answer; a firm resolve to stand by it rather than being open to giving a "
        "different answer if asked again. Given that definition, how committed you are to "
        "the answer above"
    ),
    probability_clause="you would give the same answer again if asked",
    classes=_COMMITMENT_CLASSES,
    class_ranges=_COMMITMENT_CLASS_RANGES,
    high_band=_COMMITMENT_HIGH_BAND,
    low_band=_COMMITMENT_LOW_BAND,
    highest_class="Fully committed",
    lowest_class="Not committed",
)

#: Resistance to persuasion ("how likely will you change your mind if provided
#: evidence" — concrete/conditional; an earlier "how hard would it be to
#: convince you" phrasing saturated completely on real model output, 100%
#: "Highly resistant" across 60 TriviaQA trials — see
#: `notebooks_benzon/commitment_triviaqa_validation.ipynb`). Ground truth:
#: `commitment_challenge.natural_commitment_challenge_metric` — the logit
#: drop from presenting whichever evidence argues against the model's
#: *current* answer (genuine evidence if the model was wrong, a
#: model-generated counterfeit claim if the model was right) — bound at run
#: time via `functools.partial` (`ground_truth.IntrinsicMetricThreshold`'s
#: wrinkle #2), not a bare module constant, since it needs a loaded model.
#: Previously its own "Readily/Somewhat/Rarely persuadable"/"Unpersuadable"
#: vocabulary; now shares `_COMMITMENT_CLASSES` with the other three
#: commitment sentiments (top class "Fully committed" == "you would NOT
#: change your answer even given enough contrary evidence" == the old
#: "Unpersuadable" class's meaning, just relabeled) — see
#: `_COMMITMENT_CLASSES`'s comment for why.
NATURAL_COMMITMENT = SentimentSpec(
    name="resistance to persuasion",
    criterion="how likely you would be to change your mind if provided evidence",
    probability_clause="you would NOT change your answer even given enough contrary evidence",
    classes=_COMMITMENT_CLASSES,
    class_ranges=_COMMITMENT_CLASS_RANGES,
    high_band=_COMMITMENT_HIGH_BAND,
    low_band=_COMMITMENT_LOW_BAND,
    highest_class="Fully committed",
    lowest_class="Not committed",
)

#: How nuanced/multi-sided the model's own Phase-0 answer is (plan_benzon.md
#: Part 1). Ground truth is intrinsic — Shannon entropy of the model's own
#: next-token distribution when forced to answer in a single word
#: (`metrics.answer_set_entropy`), thresholded pool-relatively like
#: `MACHINE_COMMITMENT` — not checked against an external fact.
NUANCE = SentimentSpec(
    name="nuance",
    criterion="how nuanced and multi-sided the answer above is, as opposed to flatly one-dimensional",
    probability_clause="the answer reflects a nuanced view of the question",
    classes=("Flat", "Somewhat nuanced", "Nuanced", "Highly nuanced"),
    class_ranges={
        "Flat": (0.0, 0.25),
        "Somewhat nuanced": (0.25, 0.5),
        "Nuanced": (0.5, 0.75),
        "Highly nuanced": (0.75, 1.0),
    },
    high_band=("Highly nuanced",),
    low_band=("Flat",),
    highest_class="Highly nuanced",
    lowest_class="Flat",
)

#: A/B/C follow-up-question variants for `NUANCE`, testing whether phrasing
#: explains why self-report tracks `answer_set_entropy` on the
#: ontology-trivials anchor (rho=0.301) but not on TriviaQA (rho=0.003) —
#: same pattern as `MACHINE_COMMITMENT_PARALLEL`'s A/B test: same output
#: scale, only the question differs. `NUANCE_AMBIGUITY` asks directly about
#: the *count* of plausible one-word answers instead of "nuance" as a
#: stylistic property of the elaborated answer text; `NUANCE_CERTAINTY` asks
#: about uncertainty over the specific fact, closer to `MACHINE_COMMITMENT`'s
#: self-consistency framing but scoped to "which fact" rather than "would I
#: say this again."
NUANCE_AMBIGUITY = SentimentSpec(
    name="nuance",
    criterion=(
        "how many different, genuinely plausible one-word or short-phrase answers there "
        "could be to the question above, as opposed to there being one single, unambiguous "
        "correct answer"
    ),
    probability_clause="there are multiple different plausible answers, not just one clear answer",
    classes=("Flat", "Somewhat nuanced", "Nuanced", "Highly nuanced"),
    class_ranges={
        "Flat": (0.0, 0.25),
        "Somewhat nuanced": (0.25, 0.5),
        "Nuanced": (0.5, 0.75),
        "Highly nuanced": (0.75, 1.0),
    },
    high_band=("Highly nuanced",),
    low_band=("Flat",),
    highest_class="Highly nuanced",
    lowest_class="Flat",
)

NUANCE_CERTAINTY = SentimentSpec(
    name="nuance",
    criterion=(
        "how uncertain you are about the specific fact or name that answers the question "
        "above, as opposed to being sure of exactly one answer"
    ),
    probability_clause=(
        "you are uncertain about the specific answer, as if several different answers "
        "could be equally right"
    ),
    classes=("Flat", "Somewhat nuanced", "Nuanced", "Highly nuanced"),
    class_ranges={
        "Flat": (0.0, 0.25),
        "Somewhat nuanced": (0.25, 0.5),
        "Nuanced": (0.5, 0.75),
        "Highly nuanced": (0.75, 1.0),
    },
    high_band=("Highly nuanced",),
    low_band=("Flat",),
    highest_class="Highly nuanced",
    lowest_class="Flat",
)

#: Round 2 tried two more variants pushing further in `NUANCE_AMBIGUITY`'s
#: winning direction — `NUANCE_RESAMPLE` (imagine the literal resampling
#: process `answer_set_entropy` measures) and `NUANCE_ONE_WORD` (ambiguity
#: framing scored against a forced single-word answer). Neither beat
#: `NUANCE_AMBIGUITY` on TriviaQA (`NUANCE_RESAMPLE` went slightly negative);
#: removed rather than kept alongside the four variants that remain in active
#: use — see git history for the wording and numbers.

#: Baseline-wording variant for the A/B/C/D/E follow-up test above:
#: `NUANCE`'s original phrasing performed worst of all (rho=0.003) — this
#: tests whether that's because the bare word "nuance" doesn't reliably evoke
#: "there could be multiple different plausible answers" for the model,
#: rather than a stylistic reading (hedging, multi-sided phrasing) unrelated
#: to answer-identity uncertainty. Same criterion as `NUANCE`, prefixed with
#: an explicit dictionary definition of the word itself, so the only change
#: from the original baseline is disambiguating what "nuance" means, not
#: which property is being asked about.
NUANCE_DEFINED = SentimentSpec(
    name="nuance",
    criterion=(
        '"Nuance" means: a subtle difference or distinction in meaning, expression, or '
        "opinion; a subtle quality that allows for multiple different shades of "
        "interpretation rather than one single, flat reading. Given that definition, how "
        "nuanced and multi-sided the answer above is, as opposed to flatly one-dimensional"
    ),
    probability_clause="the answer reflects a nuanced view of the question",
    classes=("Flat", "Somewhat nuanced", "Nuanced", "Highly nuanced"),
    class_ranges={
        "Flat": (0.0, 0.25),
        "Somewhat nuanced": (0.25, 0.5),
        "Nuanced": (0.5, 0.75),
        "Highly nuanced": (0.75, 1.0),
    },
    high_band=("Highly nuanced",),
    low_band=("Flat",),
    highest_class="Highly nuanced",
    lowest_class="Flat",
)

#: How varied/diverse a generated list's own items are (plan_benzon.md Part 4).
#: Ground truth is intrinsic — mean pairwise cosine distance between the
#: list's parsed items' own pooled hidden states
#: (`activations.list_embedding_variety`), same pool-relative-threshold
#: pattern as `NUANCE`, not checked against an external fact. Unlike every
#: other sentiment here, this one's Phase-0 "answer" is a plain list
#: generation (`prompts.LIST_ELICITATION_TEMPLATE`), not an answer to a
#: question — `criterion`/`probability_clause` are phrased accordingly
#: ("the items in the list above", not "the answer above"). Shared between
#: `VARIETY` and `VARIETY_DEFINED` below (same DRY reasoning as
#: `_COMMITMENT_CLASSES`): only the criterion wording differs between them.
_VARIETY_CLASSES: tuple[str, ...] = ("Uniform", "Somewhat varied", "Varied", "Highly varied")
_VARIETY_CLASS_RANGES: dict[str, tuple[float, float]] = {
    "Uniform": (0.0, 0.25),
    "Somewhat varied": (0.25, 0.5),
    "Varied": (0.5, 0.75),
    "Highly varied": (0.75, 1.0),
}

VARIETY = SentimentSpec(
    name="variety",
    criterion="how varied and diverse the items in the list above are, as opposed to near-duplicates of each other",
    probability_clause="the list's items are diverse from one another",
    classes=_VARIETY_CLASSES,
    class_ranges=_VARIETY_CLASS_RANGES,
    high_band=("Highly varied",),
    low_band=("Uniform",),
    highest_class="Highly varied",
    lowest_class="Uniform",
)

#: `VARIETY`'s own follow-up A/B test (same pattern as
#: `MACHINE_COMMITMENT_DEFINED`/`NUANCE_DEFINED`): a logit-margin diagnostic
#: on `notebooks_benzon/phase_0_calibration/4_list_elicitation.ipynb`'s constructed gate
#: lists found `VARIETY` *does* carry real signal for semantic redundancy —
#: 20 literal repeats of "A dog" score decisively "Uniform" (29.8-logit
#: margin), and 20 dog-synonyms score a measurably higher "Uniform" logit
#: than a genuinely diverse list (20.38 vs. 15.94) — but that signal is far
#: too weak (3.9-logit margin) to flip the argmax away from "Highly varied"
#: for anything short of literal string repetition. The bare word
#: "near-duplicates" is the likely culprit: nothing in `VARIETY`'s wording
#: tells the model that synonyms/rephrasings/different-breeds-of-the-same-
#: animal count as duplicates too, so it defaults to the narrowest reading
#: (identical strings only). `VARIETY_DEFINED` spells that out explicitly.
VARIETY_DEFINED = SentimentSpec(
    name="variety",
    criterion=(
        '"Variety" means: the items being genuinely distinct from each other in what they '
        "refer to, not merely written with different words. Two items that are just "
        "different names, synonyms, or rephrasings for the same underlying thing "
        '(for example, "a dog" and "a canine", or two different breeds of the same '
        "animal) count as near-duplicates for this purpose, exactly like two items that "
        "repeat the same word outright. Given that definition, how varied and diverse "
        "the items in the list above are, as opposed to near-duplicates of each other"
    ),
    probability_clause="the list's items are diverse from one another",
    classes=_VARIETY_CLASSES,
    class_ranges=_VARIETY_CLASS_RANGES,
    high_band=("Highly varied",),
    low_band=("Uniform",),
    highest_class="Highly varied",
    lowest_class="Uniform",
)

#: How evenly a 20-Questions turn's question splits the remaining candidate
#: keywords (plan_benzon.md Part 5). Ground truth is intrinsic —
#: `metrics.gini_impurity` of the actual (yes_set, no_set) partition from
#: `twenty_questions.parse_partition` — same pool-relative-threshold pattern
#: as `NUANCE`/`VARIETY`. `plan_benzon.md`'s own worked example wrote this
#: as ``("Very uneven", "Somewhat uneven", "Somewhat even", "Very even")`` —
#: a real bug, not just an unfortunate word choice: "Very uneven"/"Very
#: even" collide on "Very", and "Somewhat uneven"/"Somewhat even" collide on
#: "Somewhat", exactly the class-initial-token collision
#: `test_every_defined_sentiments_classes_have_distinct_first_words` exists
#: to catch (§2.5.1) — the same mistake this codebase's own history already
#: made once for `NATURAL_COMMITMENT` ("Very likely to change"/"Very
#: unlikely to change") and fixed by choosing distinct leading words instead.
#: This is that same fix, applied here before the bug ever gets committed:
#: same low->high evenness ordering and meaning, four genuinely distinct
#: leading words.
IMPURITY = SentimentSpec(
    name="impurity",
    criterion="how evenly the question above splits the remaining keywords into two groups",
    probability_clause="the question divides the remaining keywords close to evenly",
    lead_in=(
        "How evenly do you think your question above has split the remaining keywords "
        "into two groups? Choose one of the following classes"
    ),
    classes=("Lopsided", "Skewed", "Balanced", "Even"),
    class_ranges={
        "Lopsided": (0.0, 0.25),
        "Skewed": (0.25, 0.5),
        "Balanced": (0.5, 0.75),
        "Even": (0.75, 1.0),
    },
    high_band=("Even",),
    low_band=("Lopsided",),
    highest_class="Even",
    lowest_class="Lopsided",
)

#: Qwen's narrower distribution uses adjacent-but-separated classes (§2.7) —
#: an adjustment specific to the paper's own confidence instance, not a
#: general sentiment property.
QWEN_HIGH_BAND: tuple[str, ...] = ("Likely",)
QWEN_LOW_BAND: tuple[str, ...] = ("Unlikely",)

#: A per-sentiment Qwen low-band override was tried for `MACHINE_COMMITMENT`
#: (fit to the 65-item ontology-trivials anchor, where "Barely committed" was
#: never reached but "Mostly committed" sometimes was) and then falsified on
#: the paper's own, larger, more varied TriviaQA dataset: there, the pattern
#: flipped — "Barely committed" *was* reached (5/60 trials) and "Mostly
#: committed" was not. A single small anchor dataset isn't a reliable enough
#: basis for a per-sentiment band override; band saturation is better caught
#: generically (e.g. "no single class holds > 90% of trials") than by
#: hardcoding whichever class one particular run happened to reach.


def bands(
    model_key: str, sentiment: SentimentSpec = CONFIDENCE
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(high band, low band) for a model running ``sentiment`` (§2.7).

    The Qwen narrow-distribution adjustment only applies to the paper's own
    confidence instance, which it was validated against directly (§2.7); a
    same-shaped adjustment was tried for `MACHINE_COMMITMENT` and retracted
    after it failed to generalize to a second dataset (see the note above).
    Every other sentiment uses its own `high_band`/`low_band` unchanged.
    """
    if model_key == "qwen" and sentiment.name == "confidence":
        return QWEN_HIGH_BAND, QWEN_LOW_BAND
    return sentiment.high_band, sentiment.low_band
