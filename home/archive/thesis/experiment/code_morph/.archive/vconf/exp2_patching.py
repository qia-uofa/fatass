"""Experiment 2 — Activation patching, corrupt-then-restore (§5).

Answer information is destroyed by mean-ablating the answer token *embeddings*
(so the corruption propagates through the whole forward pass), then a single
position at a single layer is restored to its clean value.  If that position
carries information sufficient to drive confidence output, restoring it recovers
the clean behaviour despite corruption everywhere else.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from . import metrics as M
from .activations import ActivationStore, collect_activations
from .config import RunConfig
from .hooks import corrupt_embeddings, input_embeddings, mean_answer_embeddings, patch
from .interventions import (
    compute_clean_logits,
    intervention_metrics,
    numeric_midpoints,
    run_with_intervention,
)
from .models import LoadedModel, pad_batch, target_token_ids
from .pipeline import Trial
from .positions import RenderedPrompt
from .prompts import CLASSES, bands
from .results import trial_frame
from .sentiment import CONFIDENCE, SentimentSpec

#: §5.7 — the corrupt baseline is the validation gate for the answer-span mapping.
PAPER_TARGETS = {
    "clean_logit_diff": 11.5,
    "corrupt_logit_diff": 0.0,
    "corrupt_token_change_rate": 1.0,
    "PANL": {"peak_layer": 25, "logit_diff": 2.3, "confidence": 0.40, "confidence_recovery": 24.3,
             "token_change_rate": 0.78},
    "CC": {"peak_layer": 61, "logit_diff": 12.0, "confidence": 0.85, "token_change_rate": 0.05},
    "PANL+1": {"peak_layer": None, "confidence_recovery": -1.4},
}

PEAK_LAYERS = {
    "gemma-categorical": {"PANL": 25, "PANL+1": 0, "CC": 61},
    "gemma-numeric": {"PANL": 25, "PANL+1": 0, "CC": 40},
    "qwen-categorical": {"PANL": 15, "PANL+1": 27, "CC": 27},
}


def select_patching_trials(
    trials: list[Trial], n: int, model_key: str = "gemma", seed: int = 0,
    sentiment: SentimentSpec = CONFIDENCE,
) -> np.ndarray:
    """200 high-confidence trials, chosen on the original Phase-0 report (§5.4).

    Only high-confidence trials are used: corruption should substantially reduce
    confidence, and low-confidence trials are already near floor.
    """
    high_band, _ = bands(model_key, sentiment)
    eligible = [
        i for i, t in enumerate(trials)
        if (t.phase0_class or sentiment.classes[t.class_index]) in high_band
    ]
    rng = np.random.default_rng(seed)
    if len(eligible) > n:
        eligible = sorted(rng.choice(eligible, size=n, replace=False).tolist())
    return np.array(eligible, dtype=int)


def select_calibration_trials(
    trials: list[Trial], n_high: int = 50, n_low: int = 50, model_key: str = "gemma", seed: int = 0,
    sentiment: SentimentSpec = CONFIDENCE,
) -> np.ndarray:
    """A balanced 100-trial calibration set: 50 high + 50 low confidence (§5.2, §6.1)."""
    high_band, low_band = bands(model_key, sentiment)
    classes = sentiment.classes
    rng = np.random.default_rng(seed)
    high = [i for i, t in enumerate(trials) if classes[t.class_index] in high_band]
    low = [i for i, t in enumerate(trials) if classes[t.class_index] in low_band]
    pick = []
    for pool, count in ((high, n_high), (low, n_low)):
        if not pool:
            continue
        take = min(count, len(pool))
        pick.extend(rng.choice(pool, size=take, replace=False).tolist())
    return np.sort(np.array(pick, dtype=int))


def answer_spans(rendered: list[RenderedPrompt]) -> list[tuple[int, int]]:
    """Inclusive ``(first, last)`` answer-token span of each Phase-1 prompt."""
    return [(r.positions["first A"], r.positions["last A"]) for r in rendered]


@torch.no_grad()
def compute_mean_answer_embeddings(
    loaded: LoadedModel, calibration_rendered: list[RenderedPrompt], batch_size: int | None = None,
    extra_positions: list[str] | None = None,
) -> torch.Tensor:
    """Mean input embedding per answer-position index over the calibration set (§5.2).

    ``extra_positions`` prepends further positions (used by §10.2, which corrupts
    the answer-colon in addition to the answer tokens).
    """
    batch_size = batch_size or loaded.config.batch_size
    embeddings, spans = [], []
    for start in range(0, len(calibration_rendered), batch_size):
        chunk = calibration_rendered[start: start + batch_size]
        input_ids, _, _ = pad_batch(chunk, loaded.tokenizer.pad_token_id, loaded.device)
        emb = input_embeddings(loaded.model, input_ids)
        for i, r in enumerate(chunk):
            embeddings.append(emb[i])
            first, last = r.positions["first A"], r.positions["last A"]
            if extra_positions:
                first = min([first] + [r.positions[p] for p in extra_positions])
            spans.append((first, last))
    return mean_answer_embeddings(embeddings, spans)


def make_corruption(
    loaded: LoadedModel, spans_lookup: dict[int, tuple[int, int]], mean_embeddings: torch.Tensor
):
    """An ``inputs_embeds`` factory that mean-ablates each trial's answer tokens (§5.2)."""

    def factory(chunk, input_ids):
        emb = input_embeddings(loaded.model, input_ids)
        spans = [spans_lookup[id(r)] for r in chunk]
        return corrupt_embeddings(emb, spans, mean_embeddings)

    return factory


def run_patching(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    trials: list[Trial],
    clean_store: ActivationStore,
    mean_embeddings: torch.Tensor,
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = ("PANL", "PANL+1", "CC"),
    corrupt_extra_positions: list[str] | None = None,
    progress=None,
) -> tuple[pd.DataFrame, dict]:
    """Clean and corrupt baselines, then patch one (layer, position) at a time (§5.3–5.6).

    Returns the per-trial patched results and the baselines dictionary.
    """
    cfg = cfg or loaded.config
    layers = layers or cfg.layers
    target_ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind, classes=cfg.sentiment.classes)
    if cfg.prompt_kind in ("categorical", "magistral"):
        # See exp1_steering.run_steering's identical fix: numeric_midpoints(cfg.prompt_kind)
        # returns None for every categorical prompt, which makes intervention_metrics fall
        # back to metrics.MIDPOINTS -- CONFIDENCE's own 10-class array, wrong for any other
        # categorical sentiment.
        midpoints = np.array(
            [cfg.sentiment.class_midpoint[c] for c in cfg.sentiment.classes], dtype=float
        )
    else:
        midpoints = numeric_midpoints(cfg.prompt_kind)

    spans_lookup = {}
    for r in rendered:
        first, last = r.positions["first A"], r.positions["last A"]
        if corrupt_extra_positions:
            first = min([first] + [r.positions[p] for p in corrupt_extra_positions])
        spans_lookup[id(r)] = (first, last)
    corruption = make_corruption(loaded, spans_lookup, mean_embeddings)

    clean_logits = compute_clean_logits(loaded, rendered, target_ids, cfg.batch_size)
    clean_index = clean_logits.argmax(axis=1)

    corrupt_logits = run_with_intervention(
        loaded, rendered, layers[0], None, target_ids, cfg.batch_size,
        inputs_embeds_factory=corruption,
    )
    corrupt_values = intervention_metrics(corrupt_logits, clean_logits, clean_index, midpoints)
    baselines = {
        "clean_logit_diff": float(M.logit_difference(clean_logits, clean_index).mean()),
        "corrupt_logit_diff": float(corrupt_values["intervened_logit_diff"].mean()),
        "clean_confidence": float(corrupt_values["clean_confidence"].mean()),
        "corrupt_confidence": float(corrupt_values["intervened_confidence"].mean()),
        "corrupt_token_change_rate": float(corrupt_values["token_changed"].mean()),
        "corrupt_frame": trial_frame(corrupt_values, layer=-1, position="corrupt",
                                     condition="corrupt"),
    }

    frames = []
    grid = [(layer, position) for layer in layers for position in positions]
    iterator = progress(grid) if progress else grid
    for layer, position in iterator:
        clean_acts = clean_store.tensor(layer, position)

        def fn_factory(chunk, offset, position=position, clean_acts=clean_acts):
            rows = clean_acts[offset: offset + len(chunk)]
            return patch([r.positions[position] for r in chunk], rows)

        logits = run_with_intervention(
            loaded, rendered, layer, fn_factory, target_ids, cfg.batch_size,
            inputs_embeds_factory=corruption,
        )
        values = intervention_metrics(logits, clean_logits, clean_index, midpoints)
        frames.append(
            trial_frame(values, layer=layer, position=position, condition="patched")
        )
    return pd.concat(frames, ignore_index=True), baselines


def recovery_table(frame: pd.DataFrame, baselines: dict) -> pd.DataFrame:
    """Percent recovery per (layer, position) for all three metrics (§2.8 (4), §5.6)."""
    rows = []
    for (layer, position), group in frame.groupby(["layer", "position"]):
        rows.append(
            {
                "layer": layer,
                "position": position,
                "logit_diff": float(group["intervened_logit_diff"].mean()),
                "confidence": float(group["intervened_confidence"].mean()),
                "token_change_rate": float(group["token_changed"].mean()),
                "logit_diff_recovery": M.percent_recovery(
                    float(group["intervened_logit_diff"].mean()),
                    baselines["corrupt_logit_diff"],
                    baselines["clean_logit_diff"],
                ),
                "confidence_recovery": M.percent_recovery(
                    float(group["intervened_confidence"].mean()),
                    baselines["corrupt_confidence"],
                    baselines["clean_confidence"],
                ),
                "token_change_recovery": M.percent_recovery_change_rate(
                    float(group["token_changed"].mean()),
                    baselines["corrupt_token_change_rate"],
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["position", "layer"]).reset_index(drop=True)


def collect_clean_activations(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = ("PANL", "PANL+1", "CC"),
    progress=None,
) -> ActivationStore:
    """Cache the clean residual stream of the *test* trials, for patching (§2.10)."""
    cfg = cfg or loaded.config
    return collect_activations(
        loaded, rendered, layers or cfg.layers, positions,
        batch_size=cfg.batch_size, progress=progress,
    )


@torch.no_grad()
def collect_corrupt_activations(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    mean_embeddings: torch.Tensor,
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = ("PANL", "PANL+1"),
    corrupt_extra_positions: list[str] | None = None,
) -> ActivationStore:
    """Residual streams of the *corrupted* forward pass — the "pre-patch" state (§8.2 B)."""
    import numpy as np

    from .activations import ActivationStore
    from .hooks import capture_positions
    from .models import pad_batch

    cfg = cfg or loaded.config
    layers = tuple(layers or cfg.layers)
    spans_lookup = {}
    for r in rendered:
        first, last = r.positions["first A"], r.positions["last A"]
        if corrupt_extra_positions:
            first = min([first] + [r.positions[p] for p in corrupt_extra_positions])
        spans_lookup[id(r)] = (first, last)
    corruption = make_corruption(loaded, spans_lookup, mean_embeddings)

    collected = {(layer, position): [] for layer in layers for position in positions}
    for start in range(0, len(rendered), cfg.batch_size):
        chunk = rendered[start: start + cfg.batch_size]
        input_ids, attention_mask, _ = pad_batch(
            chunk, loaded.tokenizer.pad_token_id, loaded.device
        )
        embeds = corruption(chunk, input_ids)
        pos_matrix = [[r.positions[p] for p in positions] for r in chunk]
        captured: dict[int, torch.Tensor] = {}
        with capture_positions(loaded.model, layers, captured, pos_matrix):
            loaded.model(inputs_embeds=embeds, attention_mask=attention_mask)
        for layer in layers:
            rows = captured[layer].numpy()
            for j, position in enumerate(positions):
                collected[(layer, position)].append(rows[:, j, :])
    return ActivationStore(
        layers=layers,
        positions=tuple(positions),
        data={key: np.concatenate(value, axis=0) for key, value in collected.items()},
    )
