"""Variety: "how varied are the items in the list above" — self-report
counterpart to `ground_truth.ListVarianceGT`'s computed embedding spread."""

from __future__ import annotations

from .likert_om import LikertOM, intensity_classes


class VarietyOM(LikertOM):
    name = "variety"
    tags = ["baseline", "narrow", "varied"]
    criterion = "how varied and different from each other the items in the list above are"
    classes: tuple[str, ...] = intensity_classes("varied")
