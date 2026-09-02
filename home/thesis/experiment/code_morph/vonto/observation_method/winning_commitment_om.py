"""Winning commitment: a hand-overridable variant of `CommitmentOM`, for the
phase_2 steering experiment — starts out byte-for-byte identical to
`CommitmentOM` (same criterion, same classes), so nothing behaves
differently until someone deliberately edits ``criterion``/``classes`` below
by hand to try a different framing, without touching `CommitmentOM` itself
or anything else that depends on it."""

from __future__ import annotations

from .commitment_om import CommitmentOM


class WinningCommitmentOM(CommitmentOM):
    name = "winning_commitment"
    #: Own `tags` (not just inherited from `CommitmentOM`) -- required for
    #: `vonto.tagged.all_subclasses` to treat this as a concrete class rather
    #: than an abstract intermediate base (the same rule that keeps
    #: `LikertOM` itself out of `ALL`). Left out of "general" deliberately,
    #: so this one-off steering variant doesn't get pulled into the ordinary
    #: general-OM sweep (`phase_0_preparation`/`phase_1_calibration`)
    #: alongside `CommitmentOM`.
    tags = ["baseline", "uncommitted", "committed"]
