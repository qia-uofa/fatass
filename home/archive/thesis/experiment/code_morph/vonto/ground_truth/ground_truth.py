"""Base class for ground truths — grading a `Trial`'s observation against
something: a reference answer, an LLM judge, or an absolute, self-contained
property of the trial's own generation.

Concrete subclasses (each its own ``xxx_gt.py`` in this package — a reference-
comparison GT, an LLM-judged GT, an intrinsic single-trial GT, ...) are a
deliberate follow-up, not part of this first pass.
"""

from __future__ import annotations

from ..dataset import Trial


class GroundTruth:
    """One way of scoring a `Trial`'s observation, as a single ``float`` in
    ``[0, 1]`` rather than a bare ``bool`` — a binary ground truth (e.g.
    correctness) just always emits ``0.0``/``1.0``, but a continuous one (e.g.
    answer probability) can report a real graded score instead of forcing
    everything through a hard threshold first. This also means every ground
    truth here is directly comparable to a Likert self-report's own
    ``[0, 1]``-midpoint value (e.g. for a correlation), not just usable for a
    binary accuracy check.

    ``value`` grades a single trial; ``values`` grades a whole batch and is
    the one every concrete subclass must actually implement — every ground
    truth here is an absolute property of one trial's own generation (never
    relative to other trials in the batch), so ``value`` always works alone,
    but a subclass may still prefer to compute a batch at once (e.g. to
    amortize a shared setup cost).

    ``tags`` is a free-form label set for grouping/filtering ground truths
    (`vonto.ground_truth.get`) — every ground truth starts out tagged
    ``["baseline"]``, plus the two poles a ``[0, 1]`` value sits between,
    ordered low -> high (e.g. ``"incorrect"``, ``"correct"``) — a human-
    readable gloss for what a low vs. a high score actually means, folded in
    as tags too so a lookup can filter on them the same way.
    """

    name: str
    tags: list[str]

    def value(self, trial: Trial) -> float:
        return self.values([trial])[0]

    def values(self, trials: list[Trial]) -> list[float]:
        raise NotImplementedError
