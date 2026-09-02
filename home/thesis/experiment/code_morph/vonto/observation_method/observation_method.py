"""Base class for observation methods — turning a raw `Inquiry` into a
structured reading of what the model actually reports.

Concrete subclasses (each its own ``xxx_om.py`` in this package — a Likert-
scale categorical OM, a binary yes/no OM, a free-text OM, ...) are a
deliberate follow-up, not part of this first pass.
"""

from __future__ import annotations

from ..dataset import Inquiry


class ObservationMethod:
    """One way of eliciting and reading a self-report from the model.

    Kept modular: `observe` only ever needs a loaded model and the already-
    built prompt string — never the originating `Seed`/`Trial` — so an
    ObservationMethod stays reusable across any dataset that can produce a
    plain prompt, not just ones shaped a particular way.

    ``tags`` is a free-form label set for grouping/filtering observation
    methods (`vonto.observation_method.get`) — every observation method
    starts out tagged ``["baseline"]``, plus the two poles this self-report
    sits between, ordered low -> high (e.g. ``"unconfident"``, ``"confident"``)
    — a human-readable gloss for what a low vs. a high reading actually means,
    folded in as tags too so a lookup can filter on them the same way.
    """

    name: str
    tags: list[str]

    def build_prompt(self, inquiry: Inquiry) -> str:
        """Wrap ``inquiry.question`` with whatever elicitation instructions
        this observation method needs (e.g. "answer Yes or No", a Likert class
        list, ...)."""
        raise NotImplementedError

    def observe(self, loaded, prompt: str) -> object:
        """Run the model on ``prompt`` and extract the self-report."""
        raise NotImplementedError
