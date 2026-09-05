"""Experiment 3 — Activation noising / mean ablation (§6).

Each position's residual stream is replaced with the mean activation of a
balanced 100-trial calibration set (50 high + 50 low confidence), disjoint from
the test set.  Mean ablation *disrupts* the position's contribution; it does not
set confidence to a "neutral" 0.5 (§6.2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .activations import ActivationStore, collect_activations
from .config import RunConfig
from .hooks import replace
from .interventions import (
    compute_clean_logits,
    intervention_metrics,
    numeric_midpoints,
    run_with_intervention,
)
from .models import LoadedModel, target_token_ids
from .pipeline import Trial
from .positions import RenderedPrompt
from .results import trial_frame

#: §6.4 — clean logit difference ≈ 9.4; the reported disruption per position.
PAPER_TARGETS = {
    "clean_logit_diff": 9.4,
    "PANL": {"logit_diff": 8.4, "token_change_rate": 0.14, "peak_layer": 25},
    "CC": {"logit_diff": 2.8, "token_change_rate": 0.78, "peak_layer": 61},
    "PANL+1": {"logit_diff": 9.4, "token_change_rate": 0.035, "peak_layer": None},
}

PEAK_LAYERS = {
    "gemma-categorical": {"PANL": 25, "PANL+1": 15, "CC": 61},
    "gemma-numeric": {"PANL": 26, "PANL+1": 26, "CC": 61},
    "qwen-categorical": {"PANL": 11, "PANL+1": 6, "CC": 21},
}

#: §6.3 — the two metrics that best capture disruption.
PRIMARY_METRICS = ("logit_diff_change", "token_changed")


def mean_activations(
    loaded: LoadedModel,
    calibration_rendered: list[RenderedPrompt],
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = ("PANL", "PANL+1", "CC"),
    progress=None,
) -> dict[tuple[int, str], np.ndarray]:
    """Mean residual stream per (layer, position) over the calibration set (§6.1)."""
    cfg = cfg or loaded.config
    store = collect_activations(
        loaded, calibration_rendered, layers or cfg.layers, positions,
        batch_size=cfg.batch_size, progress=progress,
    )
    return {key: store.mean(*key) for key in store.data}


def run_noising(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    trials: list[Trial],
    means: dict[tuple[int, str], np.ndarray],
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = ("PANL", "PANL+1", "CC"),
    progress=None,
) -> pd.DataFrame:
    """Mean-ablate one position at one layer at a time across the sweep (§6.1)."""
    import torch

    cfg = cfg or loaded.config
    layers = layers or cfg.layers
    target_ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind)
    midpoints = numeric_midpoints(cfg.prompt_kind)
    clean_logits = compute_clean_logits(loaded, rendered, target_ids, cfg.batch_size)
    clean_index = clean_logits.argmax(axis=1)

    frames = []
    grid = [(layer, position) for layer in layers for position in positions]
    iterator = progress(grid) if progress else grid
    for layer, position in iterator:
        mean_vector = torch.tensor(means[(layer, position)], dtype=torch.float32)

        def fn_factory(chunk, offset, position=position, mean_vector=mean_vector):
            return replace([r.positions[position] for r in chunk], mean_vector)

        logits = run_with_intervention(
            loaded, rendered, layer, fn_factory, target_ids, cfg.batch_size
        )
        values = intervention_metrics(logits, clean_logits, clean_index, midpoints)
        frames.append(trial_frame(values, layer=layer, position=position, condition="noised"))
    return pd.concat(frames, ignore_index=True)


def select_noising_trials(
    trials: list[Trial], n: int, seed: int = 0, split: tuple[int, int] | None = None,
    model_key: str = "gemma",
) -> np.ndarray:
    """n test trials — *all* trials, not just high-confidence ones (§6.1).

    ``split`` applies the Qwen-specific 200 high / 100 low composition (§12.2).
    """
    rng = np.random.default_rng(seed)
    if split is None:
        index = np.arange(len(trials))
        if len(index) > n:
            index = np.sort(rng.choice(index, size=n, replace=False))
        return index
    from .prompts import CLASSES, bands

    high_band, low_band = bands(model_key)
    high = [i for i, t in enumerate(trials) if CLASSES[t.class_index] in high_band]
    low = [i for i, t in enumerate(trials) if CLASSES[t.class_index] in low_band]
    pick = []
    for pool, count in zip((high, low), split):
        if pool:
            pick.extend(rng.choice(pool, size=min(count, len(pool)), replace=False).tolist())
    return np.sort(np.array(pick, dtype=int))
