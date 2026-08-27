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
    category reflects the probability that ...".
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

#: Qwen's narrower distribution uses adjacent-but-separated classes (§2.7) —
#: an adjustment specific to the paper's own confidence instance, not a
#: general sentiment property.
QWEN_HIGH_BAND: tuple[str, ...] = ("Likely",)
QWEN_LOW_BAND: tuple[str, ...] = ("Unlikely",)


def bands(
    model_key: str, sentiment: SentimentSpec = CONFIDENCE
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(high band, low band) for a model running ``sentiment`` (§2.7).

    The Qwen narrow-distribution adjustment only applies to the paper's own
    confidence instance; any other sentiment always uses its own
    ``high_band``/``low_band`` unchanged.
    """
    if model_key == "qwen" and sentiment.name == "confidence":
        return QWEN_HIGH_BAND, QWEN_LOW_BAND
    return sentiment.high_band, sentiment.low_band
