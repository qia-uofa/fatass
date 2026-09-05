"""Answer probability (steering variant): a hand-overridable variant of
`ProbabilityGT`, for the phase_2 steering experiment -- starts out
byte-for-byte identical to `ProbabilityGT` (same ``values()``), so nothing
behaves differently until someone deliberately overrides it below by hand to
try a different computation, without touching `ProbabilityGT` itself."""

from __future__ import annotations

from .probability_gt import ProbabilityGT


class AnswerProbGT(ProbabilityGT):
    name = "answer_prob"
    #: Own `tags` (not just inherited from `ProbabilityGT`) -- required for
    #: `vonto.tagged.all_subclasses` to treat this as a concrete class.
    #: Left out of "general" deliberately, so this one-off steering variant
    #: doesn't get pulled into the ordinary general-GT sweep alongside
    #: `ProbabilityGT`.
    tags = ["baseline", "unlikely", "likely"]
