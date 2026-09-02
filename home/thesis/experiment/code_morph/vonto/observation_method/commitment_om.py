"""Commitment: "how committed are you to the answer above" — self-consistency
in spirit (would the model give this same answer again if asked)."""

from __future__ import annotations

from .likert_om import LikertOM, intensity_classes


class CommitmentOM(LikertOM):
    name = "commitment"
    tags = ["baseline", "general", "uncommitted", "committed"]
    criterion = (
        "how committed you are to the answer above"
    )
    classes: tuple[str, ...] = intensity_classes("committed")
