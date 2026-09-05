"""Confidence: "how likely is the answer above to be correct" — the paper's
own primary construct."""

from __future__ import annotations

from .likert_om import LikertOM


class ConfidenceOM(LikertOM):
    name = "confidence"
    tags = ["baseline", "general", "unconfident", "confident"]
    criterion = "how likely the answer above is to be correct"
    #: Paper's own sentence, verbatim (reproduction guidebook §2.5.1).
    range_description = "Each category reflects the probability that the answer is correct."
    classes: tuple[str, ...] = (
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
    )
