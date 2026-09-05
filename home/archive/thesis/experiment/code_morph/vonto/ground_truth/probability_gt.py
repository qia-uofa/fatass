"""Answer probability: the trial's own answer *sequence* probability — the
product of each answer token's own probability (``∏ P(token_i)`` = the
probability the model actually sampled that token from, at each step),
``exp(sum(answer_logprobs))``."""

from __future__ import annotations

import math

from ..dataset import Trial
from .ground_truth import GroundTruth


class ProbabilityGT(GroundTruth):
    """Not pool-relative: each factor is already a probability in ``[0, 1]``
    by construction — the model's own sampling probability for the token it
    actually produced at that step — so the product is too, and needs no
    cross-trial context to be meaningful (unlike a raw log-probability, which
    is unbounded and only interpretable relative to other trials).

    Being a raw product (not length-normalized) means this is dominated by
    answer *length* as much as by confidence — a confident 10-token answer
    can easily score lower than an unconfident 2-token one, since multiplying
    more sub-1 probabilities together shrinks the product regardless of how
    confident each individual token was. That's a deliberate property of
    "sequence probability" as a quantity, not a bug to normalize away here —
    a length-normalized *mean* log-probability would be a different ground
    truth, not this one.
    """

    name = "probability"
    tags = ["baseline", "general", "unlikely", "likely"]

    def values(self, trials: list[Trial]) -> list[float]:
        return [math.exp(sum(t.answer_logprobs)) if t.answer_logprobs else 0.0 for t in trials]
