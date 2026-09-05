"""Experiment 1 — Activation steering (§4).

*Where* — at which token positions and which layers — is confidence represented?
Steering vectors are the mean high-confidence minus mean low-confidence residual
stream at each (layer, position), scaled to 3% of the residual norm at that
layer and injected additively at a single position at a single layer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from . import config as cfgmod
from .activations import ActivationStore
from .config import RunConfig
from .hooks import steer
from .interventions import (
    compute_clean_logits,
    intervention_metrics,
    numeric_midpoints,
    run_with_intervention,
)
from .models import LoadedModel, target_token_ids
from .pipeline import Trial
from .positions import RenderedPrompt
from .prompts import CLASSES, bands
from .results import trial_frame

#: §4.6 — expected peak layers and magnitudes (Gemma categorical, α = 5).
PAPER_TARGETS = {
    "PANL": {"peak_layers": (21, 25), "delta_high": 0.175, "delta_low": -0.20},
    "CC": {"peak_layers": (30, 35), "delta_high": 0.40, "delta_low": -0.40},
    "PANL+1": {"peak_layers": None, "delta_high": 0.02, "delta_low": -0.02},
    "FCC": {"peak_layers": None, "delta_high": 0.02, "delta_low": -0.02},
    "AC": {"peak_layers": None, "delta_high": 0.0, "delta_low": 0.0},
}

#: §4.6 cross-model peak layers (steering).
PEAK_LAYERS = {
    "gemma-categorical": {"PANL": 25, "PANL+1": 28, "CC": 30},
    "gemma-numeric": {"PANL": 25, "PANL+1": 31, "CC": 31},
    "qwen-categorical": {"PANL": 15, "PANL+1": 1, "CC": 22},
}

BASELINE_CONFIDENCE = 0.55  # §4.6


def rank_by_confidence(trials: list[Trial]) -> np.ndarray:
    """Trial indices sorted by the model's clean verbal confidence, ascending."""
    values = np.array([t.confidence if t.confidence is not None else np.nan for t in trials])
    return np.argsort(np.nan_to_num(values, nan=-np.inf), kind="stable")


def select_vector_trials(
    trials: list[Trial], n: int = cfgmod.STEERING_VECTOR_N, require_correct: bool = True
) -> tuple[np.ndarray, np.ndarray]:
    """The 25 highest- and 25 lowest-ranked trials, answered correctly (§4.2)."""
    eligible = [
        i for i, t in enumerate(trials)
        if (t.correct or not require_correct) and t.confidence is not None
    ]
    if len(eligible) < 2 * n:
        raise ValueError(
            f"only {len(eligible)} eligible trials for {2 * n} steering-vector trials (§4.2)"
        )
    order = sorted(eligible, key=lambda i: trials[i].confidence)
    low = np.array(order[:n], dtype=int)
    high = np.array(order[-n:], dtype=int)
    return high, low


def build_steering_vectors(
    store: ActivationStore,
    high_index: np.ndarray,
    low_index: np.ndarray,
    scale_fraction: float = 0.03,
) -> dict[tuple[int, str], np.ndarray]:
    """v_high = μ(H) − μ(L), normalised to 3% of the residual norm (§4.2, §13 #5).

    The low-confidence vector is exactly the negation of the high-confidence one.
    """
    vectors: dict[tuple[int, str], np.ndarray] = {}
    for layer in store.layers:
        for position in store.positions:
            acts = store.get(layer, position)
            vector = acts[high_index].mean(axis=0) - acts[low_index].mean(axis=0)
            norm = np.linalg.norm(vector)
            if norm == 0:
                vectors[(layer, position)] = vector
                continue
            mean_residual_norm = float(np.linalg.norm(acts, axis=-1).mean())
            vectors[(layer, position)] = vector / norm * scale_fraction * mean_residual_norm
    return vectors


def select_test_trials(
    trials: list[Trial], n: int, model_key: str = "gemma", seed: int = cfgmod.SEED
) -> np.ndarray:
    """n balanced steering-test trials: half top-3 classes, half bottom-3 (§4.4)."""
    high_band, low_band = bands(model_key)
    rng = np.random.default_rng(seed)
    high = np.array(
        [i for i, t in enumerate(trials) if CLASSES[t.class_index] in high_band], dtype=int
    )
    low = np.array(
        [i for i, t in enumerate(trials) if CLASSES[t.class_index] in low_band], dtype=int
    )
    half = n // 2
    pick_high = rng.choice(high, size=min(half, len(high)), replace=False) if len(high) else high
    pick_low = rng.choice(low, size=min(n - half, len(low)), replace=False) if len(low) else low
    return np.sort(np.concatenate([pick_high, pick_low]))


def run_steering(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    trials: list[Trial],
    vectors: dict[tuple[int, str], np.ndarray],
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] | None = None,
    alphas: tuple[float, ...] | None = None,
    directions: tuple[str, ...] = ("high", "low"),
    progress=None,
) -> pd.DataFrame:
    """Steer at one position and one layer at a time across the sweep (§4.3/§4.4).

    Returns one row per (trial, layer, position, direction, α) with the three
    metrics of §2.8 relative to the trial's clean run.
    """
    cfg = cfg or loaded.config
    layers = layers or cfg.layers
    positions = positions or cfg.positions
    alphas = alphas or cfg.steering_alphas
    target_ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind)
    midpoints = numeric_midpoints(cfg.prompt_kind)
    clean_logits = compute_clean_logits(loaded, rendered, target_ids, cfg.batch_size)
    clean_index = clean_logits.argmax(axis=1)

    frames = []
    grid = [(l, p, d, a) for l in layers for p in positions for d in directions for a in alphas]
    iterator = progress(grid) if progress else grid
    for layer, position, direction, alpha in iterator:
        vector = vectors[(layer, position)]
        signed = vector if direction == "high" else -vector
        tensor = torch.tensor(signed, dtype=torch.float32)

        def fn_factory(chunk, offset, position=position, tensor=tensor, alpha=alpha):
            return steer([r.positions[position] for r in chunk], tensor, alpha)

        logits = run_with_intervention(
            loaded, rendered, layer, fn_factory, target_ids, cfg.batch_size
        )
        values = intervention_metrics(logits, clean_logits, clean_index, midpoints)
        frames.append(
            trial_frame(values, layer=layer, position=position, direction=direction,
                        alpha=alpha, condition=f"{direction} α={alpha:g}")
        )
    return pd.concat(frames, ignore_index=True)
