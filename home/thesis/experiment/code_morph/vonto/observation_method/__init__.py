"""Observation methods — one file per concrete subclass (``xxx_om.py``),
alongside the shared base class in `observation_method.py`.

``ALL`` is every concrete `ObservationMethod` subclass; ``get`` looks them up
by tag (`vonto.tagged.get`) — e.g. ``get(ALL)(["confident"])``.
"""

from ..tagged import all_subclasses, get
from .challenge_om import ChallengeOM
from .commitment_om import CommitmentOM
from .confidence_om import ConfidenceOM
from .impurity_om import ImpurityOM
from .likert_om import LikertOM
from .nuance_om import NuanceOM
from .observation_method import ObservationMethod
from .variety_om import VarietyOM
from .winning_commitment_om import WinningCommitmentOM

ALL = all_subclasses(ObservationMethod)

__all__ = [
    "ObservationMethod",
    "LikertOM",
    "ConfidenceOM",
    "CommitmentOM",
    "NuanceOM",
    "ChallengeOM",
    "VarietyOM",
    "ImpurityOM",
    "WinningCommitmentOM",
    "ALL",
    "get",
]
