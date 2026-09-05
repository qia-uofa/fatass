"""Ground truths — one file per concrete subclass (``xxx_gt.py``), alongside
the shared base class in `ground_truth.py`.

``ALL`` is every concrete `GroundTruth` subclass; ``get`` looks them up by tag
(`vonto.tagged.get`) — e.g. ``get(ALL)(["correct"])``.
"""

from ..tagged import all_subclasses, get
from .answer_prob_gt import AnswerProbGT
from .challenge_gt import ChallengeGT
from .correctness_gt import CorrectnessGT
from .entropy_gt import EntropyGT
from .ground_truth import GroundTruth
from .impurity_gt import ImpurityGT
from .list_variance_gt import ListVarianceGT
from .probability_gt import ProbabilityGT
from .temperature_gt import TemperatureGT

ALL = all_subclasses(GroundTruth)

__all__ = [
    "GroundTruth",
    "CorrectnessGT",
    "ProbabilityGT",
    "EntropyGT",
    "ChallengeGT",
    "ListVarianceGT",
    "ImpurityGT",
    "TemperatureGT",
    "AnswerProbGT",
    "ALL",
    "get",
]
