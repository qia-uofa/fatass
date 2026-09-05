"""Experiment 8 — Attention blocking / attention knockout (§11).

Attention edges ``t ← s`` are zeroed across all heads over a **window of 12
consecutive layers** centred at each x-axis position (§11.2), which is what
exposes a pathway that is redundant across nearby layers.  The primary analysis
uses the minimal numeric (0–9) prompt, because the full categorical prompt's
hundred-plus intermediate template tokens mask the direct CC→PANL edge (§11.3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from . import metrics as M
from .attention import (
    CATEGORICAL_PATHWAYS,
    MINIMAL_PATHWAYS,
    attention_knockout,
    build_block_mask,
    pathway_edges,
    window_layers,
)
from .config import RunConfig
from .interventions import compute_clean_logits, intervention_metrics, numeric_midpoints
from .models import LoadedModel, pad_batch, target_token_ids
from .pipeline import Trial
from .positions import RenderedPrompt
from .results import trial_frame

#: §11.6 — minimal numeric prompt.
PAPER_TARGETS_MINIMAL = {
    "CC->PANL": {"token_change_rate": 0.21, "logit_diff_change": -0.80, "peak_layers": (30, 36)},
    "CC->Q+A": {"token_change_rate": 0.10, "logit_diff_change": -0.2},
    "CC->PANL+1": {"token_change_rate": 0.10, "logit_diff_change": 0.0},
    "PANL->A": {"token_change_rate": 0.20, "logit_diff_change": -0.85, "peak_layers": (22, 28)},
    "PANL->last_A": {"token_change_rate": 0.20, "logit_diff_change": -0.75, "peak_layers": (22, 28)},
}

#: §11.7 — full categorical prompt.
PAPER_TARGETS_CATEGORICAL = {
    "CC->NL+1": {"token_change_rate": 0.10, "logit_diff_change": 0.0},
    "CC->NL": {"token_change_rate": 0.09, "logit_diff_change": -0.3},
    "CC->A": {"token_change_rate": 0.12, "logit_diff_change": -0.2},
    "CC->Q": {"token_change_rate": 0.11, "logit_diff_change": -0.2},
    "CC->Q+A": {"token_change_rate": 0.12, "logit_diff_change": -0.4},
    "ALL->NL": {"token_change_rate": 0.19, "logit_diff_change": -0.9},
    "ALL->last_A": {"token_change_rate": 0.51, "logit_diff_change": -5.3},
    "ALL->NL+last_A": {"token_change_rate": 0.48, "logit_diff_change": -5.3},
    "ALL->last_A_keepNL": {"token_change_rate": 0.22, "logit_diff_change": -1.6},
    "ALL->A": {"token_change_rate": 0.685, "logit_diff_change": -8.0},
    "ALL->NL+A": {"token_change_rate": 0.59, "logit_diff_change": -7.3},
    "ALL->A_keepNL": {"token_change_rate": 0.455, "logit_diff_change": -4.3},
}

#: §11.8 — the sequential flow the experiment establishes.
INFORMATION_FLOW = "answer tokens → PANL (L22–28) → CC (L30–36) → unembedding (L61)"
LAYER_GAP = (6, 8)  # §11.8 conclusion 3


@torch.no_grad()
def run_blocking(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    trials: list[Trial],
    cfg: RunConfig | None = None,
    pathways: tuple[str, ...] = MINIMAL_PATHWAYS,
    sweep: tuple[int, ...] | None = None,
    window: int | None = None,
    progress=None,
) -> pd.DataFrame:
    """Block each pathway across each 12-layer window and measure the disruption (§11.4/§11.5).

    Requires the model to have been loaded with ``attn_implementation="eager"``.
    """
    cfg = cfg or loaded.config
    sweep = sweep or cfg.attention_sweep
    window = window or cfg.attention_window
    sweep = tuple(center for center in sweep if center < loaded.n_layers)
    target_ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind)
    midpoints = numeric_midpoints(cfg.prompt_kind)
    clean_logits = compute_clean_logits(loaded, rendered, target_ids, cfg.batch_size)
    clean_index = clean_logits.argmax(axis=1)

    frames = []
    grid = [(center, pathway) for center in sweep for pathway in pathways]
    iterator = progress(grid) if progress else grid
    for center, pathway in iterator:
        layers = window_layers(center, loaded.n_layers, window)
        blocked_logits = []
        for start in range(0, len(rendered), cfg.batch_size):
            chunk = rendered[start: start + cfg.batch_size]
            input_ids, attention_mask, lengths = pad_batch(
                chunk, loaded.tokenizer.pad_token_id, loaded.device
            )
            edges = [pathway_edges(r, pathway) for r in chunk]
            block_mask = build_block_mask(
                edges, input_ids.shape[1], loaded.device, loaded.model.dtype
            )
            with attention_knockout(loaded.model, layers, block_mask, attention_mask):
                logits = loaded.model(input_ids=input_ids, attention_mask=attention_mask).logits
            idx = torch.tensor([n - 1 for n in lengths], device=logits.device)
            final = logits[torch.arange(len(chunk), device=logits.device), idx, :].float()
            blocked_logits.append(final[:, target_ids].cpu().numpy())
        values = intervention_metrics(
            np.concatenate(blocked_logits, axis=0), clean_logits, clean_index, midpoints
        )
        frames.append(
            trial_frame(values, layer=center, position=pathway, condition=pathway,
                        window_lo=layers[0], window_hi=layers[-1])
        )
    return pd.concat(frames, ignore_index=True)


def keep_nl_effect(summary: pd.DataFrame, metric: str = "token_changed_mean") -> pd.DataFrame:
    """How much preserving the PANL→answer pathway reduces the disruption (§11.8 item 3)."""
    rows = []
    for base, kept in (("ALL->last_A", "ALL->last_A_keepNL"), ("ALL->A", "ALL->A_keepNL")):
        for layer in sorted(summary["layer"].unique()):
            at_layer = summary[summary["layer"] == layer].set_index("condition")
            if base in at_layer.index and kept in at_layer.index:
                rows.append(
                    {
                        "layer": layer,
                        "blocked": base,
                        "blocked_value": float(at_layer.loc[base, metric]),
                        "keepNL_value": float(at_layer.loc[kept, metric]),
                        "reduction": float(at_layer.loc[base, metric] - at_layer.loc[kept, metric]),
                    }
                )
    return pd.DataFrame(rows)


def pathway_peak_layers(summary: pd.DataFrame, metric: str = "token_changed_mean") -> dict[str, int]:
    """Layer window centre at which each pathway's disruption peaks (§11.6)."""
    out = {}
    for condition, group in summary.groupby("condition"):
        out[str(condition)] = int(group.loc[group[metric].idxmax(), "layer"])
    return out


def exceeds_control(
    frame: pd.DataFrame, pathway: str, control: str, layer: int, metric: str = "token_changed"
) -> dict:
    """Paired comparison of a pathway against its control on matched trials (§13 #11)."""
    at_layer = frame[frame["layer"] == layer]
    a = at_layer[at_layer["condition"] == pathway].sort_values("trial")[metric].to_numpy()
    b = at_layer[at_layer["condition"] == control].sort_values("trial")[metric].to_numpy()
    size = min(len(a), len(b))
    return M.paired_comparison(a[:size], b[:size])


ALL_PATHWAYS = {"minimal": MINIMAL_PATHWAYS, "categorical": CATEGORICAL_PATHWAYS}
