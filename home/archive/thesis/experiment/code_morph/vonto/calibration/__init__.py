"""Calibration — the vonto reproduction of the paper's Experiment 0
(reproduction guidebook §3): establishing a meaningful, reasonably calibrated
verbal confidence signal. Four files:

- `generation` (paper's Phase 0): run an `Inquiry` against a loaded model,
  producing the `Trial` every ground truth reads.
- `observation` (paper's Phase 1): re-insert the model's own answer and
  elicit an `ObservationMethod`'s self-report about it.
- `calibration`: the actual {dataset} x {observation method} x {ground truth}
  cross-product analysis built on top of the two above — cached generation,
  cached observation/grading, and the resulting correlation matrix.
- `steering` (paper's Experiment 1, reproduction guidebook §4): extract a
  steering vector from high-/low-*self-reported* trials' own residual-stream
  activations at one (layer, position) — PANL, PANL+1, FCC, or CC — inject
  it back in (both directions), and measure the shift it causes in the same
  self-report, on a disjoint set of test trials. AC (a Phase-0-prompt
  position, mechanistically different from the other four) gets its own,
  smaller-scale functions (`build_ac_steering_vector`/`ac_steering_effect`),
  since testing it means regenerating the answer under intervention rather
  than a single forward pass.

(The paper's own "Phase 0"/"Phase 1" names already mean something else one
level up in vonto — dataset-prep vs. calibration-experiment — so `generation`/
`observation` are named after what each stage actually *does* instead.)
"""

from .calibration import (
    correlation_matrix,
    generate_disjoint_pools,
    generate_trials,
    grade_all,
    observe_all,
    run_calibration,
)
from .generation import generate_trial
from .observation import observe_trial
from .steering import (
    POSITIONS,
    ac_steering_effect,
    build_ac_steering_vector,
    build_steering_vector,
    observe_with_steering,
    residual_at_ac,
    residual_at_position,
    select_balanced_test_trials,
    steering_effect,
)

__all__ = [
    "generate_trial",
    "observe_trial",
    "generate_trials",
    "generate_disjoint_pools",
    "observe_all",
    "grade_all",
    "correlation_matrix",
    "run_calibration",
    "POSITIONS",
    "residual_at_position",
    "build_steering_vector",
    "select_balanced_test_trials",
    "observe_with_steering",
    "steering_effect",
    "residual_at_ac",
    "build_ac_steering_vector",
    "ac_steering_effect",
]
