"""Nuance: "how nuanced and multi-sided is the answer above" — how many
different, genuinely plausible answers there might have been."""

from __future__ import annotations

from .likert_om import LikertOM, intensity_classes


class NuanceOM(LikertOM):
    name = "nuance"
    tags = ["baseline", "general", "flat", "nuanced"]
    criterion = (
        "how nuanced and multi-sided the answer above is, as opposed to flatly one-dimensional, "
        "which means how many different, genuinely plausible answers there might have been"
    )
    classes: tuple[str, ...] = intensity_classes("nuanced")
