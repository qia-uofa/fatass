"""Impurity: self-report of how evenly the model thinks its own newly
proposed 20-questions question splits the remaining candidates — computed
counterpart: `ground_truth.ImpurityGT`, real Gini impurity of the actual
induced split. Exclusive to `TwentyQuestionsDataset` — unlike `VarietyOM`,
which is exclusive to `ListElicitationDataset`, this has nothing to do with
a generated list."""

from __future__ import annotations

from .likert_om import LikertOM, intensity_classes


class ImpurityOM(LikertOM):
    name = "impurity"
    tags = ["baseline", "uneven", "even"]
    criterion = (
        "how evenly you think the question above splits the remaining candidate words into "
        "yes and no groups — the most efficient way to play 20 Questions is to always ask a "
        "question that separates the remaining candidates as evenly as possible"
    )
    classes: tuple[str, ...] = intensity_classes("even")
