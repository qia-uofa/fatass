"""Experiment 5 — Out-of-distribution control analysis (§8).

A **mandatory** control: do the interventions merely push the residual stream
out of distribution?  The natural pairwise variability of activations (cosine
similarity and norm ratio, 5th/95th percentiles over ≥100,000 random pairs from
the activation-collection set) is compared against the drift each intervention
induces at layer 25, at both PANL and PANL+1.
"""

from __future__ import annotations

import numpy as np

from . import config as cfgmod
from .activations import ActivationStore

#: §8.2 — the natural distribution and the per-intervention drift at layer 25.
PAPER_TARGETS = {
    "natural_cosine_p5_p95": (0.997, 1.000),
    "natural_norm_ratio_p5_p95": (0.90, 1.11),
    "intervention_cosine_min": 0.99,
    "intervention_norm_ratio_range": (0.91, 1.10),
    "patching": {"PANL": {"cosine": 0.999, "norm_ratio": 0.94},
                 "PANL+1": {"cosine": 0.999, "norm_ratio": 0.98}},
    "noising": {"PANL": {"cosine": 0.999, "norm_ratio": 0.995},
                "PANL+1": {"cosine": 0.999, "norm_ratio": 0.999}},
    # The dissociation that makes the argument (§8.3).
    "confidence_recovery": {"PANL": 24.3, "PANL+1": -1.4},
}

OOD_LAYER = 25  # the peak-effect layer the control is computed at (§8.1)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity between two ``(n, d)`` activation matrices."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    num = (a * b).sum(axis=-1)
    denom = np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(denom > 0, num / denom, np.nan)


def norm_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise ratio of L2 norms ‖a‖/‖b‖."""
    na = np.linalg.norm(np.asarray(a, dtype=np.float64), axis=-1)
    nb = np.linalg.norm(np.asarray(b, dtype=np.float64), axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(nb > 0, na / nb, np.nan)


def natural_variability(
    store: ActivationStore,
    layer: int = OOD_LAYER,
    position: str = "PANL",
    n_pairs: int = cfgmod.OOD_PAIRS,
    seed: int = 0,
) -> dict[str, tuple[float, float]]:
    """5th/95th percentiles of pairwise cosine and norm ratio over random pairs (§8.1)."""
    acts = store.get(layer, position)
    n = len(acts)
    if n < 2:
        raise ValueError("need at least two trials for pairwise variability")
    rng = np.random.default_rng(seed)
    i = rng.integers(0, n, size=n_pairs)
    j = rng.integers(0, n, size=n_pairs)
    keep = i != j
    i, j = i[keep], j[keep]
    cos = cosine_similarity(acts[i], acts[j])
    ratio = norm_ratio(acts[i], acts[j])
    return {
        "cosine_p5_p95": (float(np.nanpercentile(cos, 5)), float(np.nanpercentile(cos, 95))),
        "norm_ratio_p5_p95": (float(np.nanpercentile(ratio, 5)), float(np.nanpercentile(ratio, 95))),
        "n_pairs": int(len(i)),
    }


def intervention_drift(clean: np.ndarray, perturbed: np.ndarray) -> dict[str, float]:
    """Mean cosine similarity and norm ratio between perturbed and clean activations (§8.2)."""
    cos = cosine_similarity(perturbed, clean)
    ratio = norm_ratio(perturbed, clean)
    return {
        "cosine_mean": float(np.nanmean(cos)),
        "cosine_min": float(np.nanmin(cos)),
        "norm_ratio_mean": float(np.nanmean(ratio)),
        "norm_ratio_min": float(np.nanmin(ratio)),
        "norm_ratio_max": float(np.nanmax(ratio)),
    }


def steering_drift(
    store: ActivationStore,
    vectors: dict[tuple[int, str], np.ndarray],
    layer: int = OOD_LAYER,
    positions: tuple[str, ...] = ("PANL", "PANL+1"),
    alphas: tuple[float, ...] = (2.0, 5.0),
    directions: tuple[str, ...] = ("high", "low"),
) -> dict[tuple[str, str, float], dict[str, float]]:
    """Clean vs steered activation drift, per (position, direction, α) (§8.2 A)."""
    out = {}
    for position in positions:
        clean = store.get(layer, position)
        for direction in directions:
            for alpha in alphas:
                vector = vectors[(layer, position)]
                signed = vector if direction == "high" else -vector
                out[(position, direction, alpha)] = intervention_drift(
                    clean, clean + alpha * signed
                )
    return out


def noising_drift(
    store: ActivationStore,
    means: dict[tuple[int, str], np.ndarray],
    layer: int = OOD_LAYER,
    positions: tuple[str, ...] = ("PANL", "PANL+1"),
) -> dict[str, dict[str, float]]:
    """Clean vs mean-replacement drift (§8.2 C)."""
    return {
        position: intervention_drift(
            store.get(layer, position),
            np.broadcast_to(means[(layer, position)], store.get(layer, position).shape),
        )
        for position in positions
    }


def patching_drift(
    clean_store: ActivationStore,
    corrupt_store: ActivationStore,
    layer: int = OOD_LAYER,
    positions: tuple[str, ...] = ("PANL", "PANL+1"),
) -> dict[str, dict[str, float]]:
    """"Pre-patch" similarity: clean-cached vs corruption-propagated activation (§8.2 B)."""
    return {
        position: intervention_drift(
            clean_store.get(layer, position), corrupt_store.get(layer, position)
        )
        for position in positions
    }


def within_natural_range(drift: dict[str, float], natural: dict[str, tuple[float, float]]) -> bool:
    """Whether an intervention's drift stays inside the natural pairwise distribution (§8.3)."""
    cos_lo, _ = natural["cosine_p5_p95"]
    nr_lo, nr_hi = natural["norm_ratio_p5_p95"]
    return bool(
        drift["cosine_min"] >= cos_lo
        and drift["norm_ratio_min"] >= nr_lo
        and drift["norm_ratio_max"] <= nr_hi
    )
