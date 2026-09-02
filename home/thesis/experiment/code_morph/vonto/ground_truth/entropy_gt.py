"""Answer entropy: the entropy of the distribution over *all possible answers*
the model could generate from this one prompt — the Shannon entropy of its
own next-token distribution at each answer step, summed across the answer."""

from __future__ import annotations

from ..dataset import Trial
from .ground_truth import GroundTruth


class EntropyGT(GroundTruth):
    """Not pool-relative: by the chain rule, the entropy of the whole answer
    sequence's distribution is exactly the sum of each step's own conditional
    entropy (``H(answer) = sum_i H(token_i | token_<i)``) — a property of this
    one prompt's own generation, needing no other trial for context.

    Reads ``trial.answer_entropies`` (one full-distribution entropy per answer
    token, recorded during the original generation — see `Trial`), the same
    way `ProbabilityGT` reads ``answer_logprobs``. Higher means the model had
    more live alternatives at each step, i.e. less committed to this
    particular answer; lower means it saw few real alternatives.
    """

    name = "entropy"
    tags = ["baseline", "general", "certain", "uncertain"]

    def values(self, trials: list[Trial]) -> list[float]:
        return [sum(t.answer_entropies) if t.answer_entropies else 0.0 for t in trials]
