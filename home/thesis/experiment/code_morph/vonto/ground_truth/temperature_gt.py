"""Temperature: the sampling temperature stored on the list-elicitation
seed itself — not computed from the trial's response at all, just read
straight off ``trial.seed.temperature``. Exclusive to
`ListElicitationDataset` (the only seed type that carries one)."""

from __future__ import annotations

from ..dataset import Trial
from .ground_truth import GroundTruth


class TemperatureGT(GroundTruth):
    """A control column, not a real ground truth about the model's own
    behavior the way every other GT here is: ``ListElicitationSeed.temperature``
    is drawn once, before generation ever happens
    (``rng.uniform(0.0, 1.0)``, see `ListElicitationDataset.generate`) — the
    model never sees or is told this value, so any real self-report OM
    correlating against it should read approximately zero; a nonzero
    correlation would flag a leak (e.g. the sampling temperature somehow
    biasing the response in a way an OM picks up on) rather than a genuine
    calibration signal. Requires the seed type to actually carry a
    ``temperature`` field; raises loudly on a seed type that doesn't.
    """

    name = "temperature"
    tags = ["baseline", "cold", "hot"]

    def values(self, trials: list[Trial]) -> list[float]:
        out = []
        for trial in trials:
            temperature = getattr(trial.seed, "temperature", None)
            if temperature is None:
                raise ValueError(
                    f"{type(trial.seed).__name__} has no 'temperature' field — TemperatureGT "
                    "needs a seed that carries one"
                )
            out.append(float(temperature))
        return out
