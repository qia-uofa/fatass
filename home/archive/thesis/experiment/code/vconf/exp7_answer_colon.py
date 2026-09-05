"""Experiment 7 — The answer-colon (AC) control experiments (§10).

AC is the position whose final-layer residual stream is transformed by the
unembedding matrix into the logits over the *first answer token*, so it is where
generation-time evidence lives.  Under a first-order account, interventions
there should modulate verbal confidence.  All four analyses are run at AC on the
**same trials** as the corresponding PANL analyses.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfgmod
from . import exp1_steering, exp2_patching, exp3_noising
from .activations import ActivationStore
from .exp6_probing import probe_confidence
from .pipeline import Trial

#: §10.3 — AC is null everywhere PANL is substantial.
PAPER_TARGETS = {
    "steering": {"AC": "no significant confidence change", "PANL": "substantial"},
    "patching": {"AC": "no recovery", "PANL": "partial recovery"},
    "noising": {"AC": "no disruption (comparable to PANL+1)", "PANL": "partial disruption"},
    "decoding_r2": {"AC": 0.2, "PANL": 0.75},
}

#: The positions compared in every AC analysis.
POSITIONS = ("AC", "PANL", "PANL+1")

RIDGE_ALPHA_GRID = (0.1, 1.0, 10.0, 100.0, 1000.0)


def run_ac_steering(loaded, rendered, trials, vectors, cfg=None, layers=None,
                    positions=POSITIONS, **kwargs) -> pd.DataFrame:
    """Steering at AC, on the same trials and protocol as §4 (§10.2 item 1)."""
    return exp1_steering.run_steering(
        loaded, rendered, trials, vectors, cfg=cfg, layers=layers, positions=positions, **kwargs
    )


def run_ac_patching(loaded, rendered, trials, clean_store, mean_embeddings, cfg=None,
                    layers=None, positions=POSITIONS, **kwargs):
    """Patching at AC — the AC token is corrupted *in addition to* the answer tokens.

    Because AC precedes the answer, corrupting only answer tokens would leave AC
    clean and the restore test meaningless (§10.2 item 2).
    """
    return exp2_patching.run_patching(
        loaded, rendered, trials, clean_store, mean_embeddings, cfg=cfg, layers=layers,
        positions=positions, corrupt_extra_positions=["AC"], **kwargs
    )


def run_ac_noising(loaded, rendered, trials, means, cfg=None, layers=None,
                   positions=POSITIONS, **kwargs) -> pd.DataFrame:
    """Mean ablation at AC, identical protocol to §6 (§10.2 item 3)."""
    return exp3_noising.run_noising(
        loaded, rendered, trials, means, cfg=cfg, layers=layers, positions=positions, **kwargs
    )


def tune_ridge_alpha(
    X: np.ndarray, y: np.ndarray, alphas: tuple[float, ...] = RIDGE_ALPHA_GRID,
    seed: int = cfgmod.SEED,
) -> tuple[float, dict[float, float]]:
    """Select the Ridge penalty that maximises cross-validated R² on ``X``.

    §10.2 item 4 requires tuning on **AC** and then reusing that α for PANL and
    PANL+1, which deliberately biases the comparison in AC's favour.
    """
    scores = {alpha: probe_confidence(X, y, alpha=alpha, seed=seed) for alpha in alphas}
    best = max(scores, key=scores.get)
    return best, scores


def ac_decoding_comparison(
    store: ActivationStore,
    trials: list[Trial],
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = POSITIONS,
    alphas: tuple[float, ...] = RIDGE_ALPHA_GRID,
    seed: int = cfgmod.SEED,
    progress=None,
) -> tuple[pd.DataFrame, dict]:
    """Layerwise Ridge R² for verbal confidence at AC, PANL and PANL+1 (§10.2 item 4).

    The penalty is chosen on AC (at the layer where AC decodes best) and reused
    unchanged for the other positions.
    """
    layers = layers or store.layers
    y = np.array([t.confidence for t in trials], dtype=float)

    tuned: dict[int, float] = {}
    per_layer_scores = {}
    for layer in layers:
        best, scores = tune_ridge_alpha(store.get(layer, "AC"), y, alphas=alphas, seed=seed)
        tuned[layer] = best
        per_layer_scores[layer] = scores
    best_layer = max(tuned, key=lambda layer: per_layer_scores[layer][tuned[layer]])
    alpha = tuned[best_layer]

    rows = []
    grid = [(layer, position) for layer in layers for position in positions]
    iterator = progress(grid) if progress else grid
    for layer, position in iterator:
        rows.append(
            {
                "layer": layer,
                "position": position,
                "confidence_r2": probe_confidence(
                    store.get(layer, position), y, alpha=alpha, seed=seed
                ),
                "alpha": alpha,
            }
        )
    info = {"alpha": alpha, "tuned_on": "AC", "tuned_at_layer": best_layer,
            "alpha_scores": per_layer_scores[best_layer]}
    return pd.DataFrame(rows), info
