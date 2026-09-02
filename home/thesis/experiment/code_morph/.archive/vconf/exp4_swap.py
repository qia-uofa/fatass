"""Experiment 4 — Activation swap / interchange intervention (§7).

A donor trial's PANL residual stream is transplanted into a recipient trial
whose question and answer are untouched.  Crossing recipient confidence
(high/low) with donor confidence (high/low) gives the 2×2 design whose
same-confidence cells control for generic cross-trial substitution effects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from . import config as cfgmod
from .activations import ActivationStore
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
from .prompts import CLASSES, bands
from .results import trial_frame
from .sentiment import CONFIDENCE, SentimentSpec

#: The 2×2 factorial of §7.2 — the first letter is the recipient.
CONDITIONS = ("H->H", "L->L", "H->L", "L->H")
CONTROL_CONDITIONS = ("H->H", "L->L")
CROSS_CONDITIONS = ("H->L", "L->H")

#: §7.5 — expected effects at PANL, peaking at layer 26.
PAPER_TARGETS = {
    "peak_layer": 26,
    "L->H": {"confidence_change": 0.21, "logit_diff_change": -1.2, "token_change_rate": 0.37},
    "H->L": {"confidence_change": -0.09, "logit_diff_change": -2.0, "token_change_rate": 0.30},
    "H->H": {"confidence_change": 0.0, "logit_diff_change": -1.1, "token_change_rate": 0.15},
    "L->L": {"confidence_change": 0.0, "logit_diff_change": -0.3, "token_change_rate": 0.12},
}

PEAK_LAYERS = {
    "gemma-categorical": {"PANL": 26, "PANL+1": 31, "CC": 61},
    "gemma-numeric": {"PANL": 26, "PANL+1": 31, "CC": 61},
    "qwen-categorical": {"PANL": 15, "PANL+1": 15, "CC": 27},
}

#: §7.3 — reported donor/recipient matching quality to reproduce.
MATCHING_TARGETS = {
    "question_bin_match": 1.0,
    "answer_bin_match": (0.94, 1.0),
    "mean_abs_question_delta": (1.5, 2.7),
    "mean_abs_answer_delta": (0.3, 0.5),
}


def confidence_pools(
    trials: list[Trial], model_key: str = "gemma", sentiment: SentimentSpec = CONFIDENCE
) -> tuple[np.ndarray, np.ndarray]:
    """Indices of high- and low-confidence trials by the model's clean report (§7.3)."""
    high_band, low_band = bands(model_key, sentiment)
    classes = sentiment.classes
    high = np.array([i for i, t in enumerate(trials) if classes[t.class_index] in high_band], dtype=int)
    low = np.array([i for i, t in enumerate(trials) if classes[t.class_index] in low_band], dtype=int)
    return high, low


def sample_recipients(pool: np.ndarray, n: int, seed: int = 0) -> np.ndarray:
    """Draw ``n`` recipients, sampling **with replacement** when the pool is short (§7.3)."""
    rng = np.random.default_rng(seed)
    if len(pool) == 0:
        raise ValueError("empty recipient pool")
    replace_flag = len(pool) < n
    return rng.choice(pool, size=n, replace=replace_flag)


def quantile_bins(values: np.ndarray, n_bins: int = cfgmod.DONOR_QUANTILE_BINS) -> np.ndarray:
    """Assign each value to one of ``n_bins`` quantile bins (§7.3, §13 #10)."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return np.zeros(0, dtype=int)
    edges = np.quantile(values, np.linspace(0, 1, n_bins + 1)[1:-1])
    return np.digitize(values, edges, right=False)


def prompt_lengths(rendered: list[RenderedPrompt]) -> tuple[np.ndarray, np.ndarray]:
    """Tokenised question length and answer length per trial (§7.3)."""
    from .positions import span_to_tokens

    q_len, a_len = [], []
    for r in rendered:
        first, last = span_to_tokens(r.offsets, r.spans["question"])
        q_len.append(last - first + 1)
        a_len.append(r.positions["last A"] - r.positions["first A"] + 1)
    return np.array(q_len), np.array(a_len)


def match_donors(
    recipients: np.ndarray,
    donor_pool: np.ndarray,
    q_len: np.ndarray,
    a_len: np.ndarray,
    n_bins: int = cfgmod.DONOR_QUANTILE_BINS,
    seed: int = 0,
) -> tuple[np.ndarray, dict]:
    """Match donors to recipients on question- and answer-length quantile bins (§7.3).

    Prefers a donor in the same (question bin, answer bin) cell, then the same
    question bin, then any donor; returns the matching-quality statistics the
    paper reports.
    """
    rng = np.random.default_rng(seed)
    q_bin, a_bin = quantile_bins(q_len, n_bins), quantile_bins(a_len, n_bins)
    donors = np.empty(len(recipients), dtype=int)
    q_match, a_match = [], []
    for k, recipient in enumerate(recipients):
        exact = [
            d for d in donor_pool
            if q_bin[d] == q_bin[recipient] and a_bin[d] == a_bin[recipient]
        ]
        if exact:
            candidates = exact
        else:
            # No donor in the same cell: take the ones closest in bin distance,
            # so the reported |ΔL_Q| / |ΔL_A| stay as small as the pool allows.
            distances = {
                int(d): abs(int(q_bin[d]) - int(q_bin[recipient]))
                + abs(int(a_bin[d]) - int(a_bin[recipient]))
                for d in donor_pool
            }
            best = min(distances.values())
            candidates = [d for d, distance in distances.items() if distance == best]
        donor = int(rng.choice(candidates))
        donors[k] = donor
        q_match.append(q_bin[donor] == q_bin[recipient])
        a_match.append(a_bin[donor] == a_bin[recipient])
    stats = {
        "question_bin_match": float(np.mean(q_match)) if q_match else float("nan"),
        "answer_bin_match": float(np.mean(a_match)) if a_match else float("nan"),
        "mean_abs_question_delta": float(np.abs(q_len[donors] - q_len[recipients]).mean()),
        "mean_abs_answer_delta": float(np.abs(a_len[donors] - a_len[recipients]).mean()),
    }
    return donors, stats


def build_swap_design(
    trials: list[Trial],
    rendered: list[RenderedPrompt],
    n: int = 400,
    model_key: str = "gemma",
    seed: int = 0,
    n_bins: int = cfgmod.DONOR_QUANTILE_BINS,
    sentiment: SentimentSpec = CONFIDENCE,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], dict[str, dict]]:
    """Recipients and length-matched donors for each of the four conditions (§7.2/§7.3).

    The **same** high recipients are used in H→H and H→L, and the same low
    recipients in L→L and L→H, which makes the control a within-trial comparison.
    """
    high, low = confidence_pools(trials, model_key, sentiment)
    q_len, a_len = prompt_lengths(rendered)
    recipients = {
        "H": sample_recipients(high, n, seed=seed),
        "L": sample_recipients(low, n, seed=seed + 1),
    }
    design, stats = {}, {}
    for condition in CONDITIONS:
        recipient_band, donor_band = condition.split("->")
        donor_pool = high if donor_band == "H" else low
        donors, quality = match_donors(
            recipients[recipient_band], donor_pool, q_len, a_len, n_bins=n_bins,
            seed=seed + hash(condition) % 1000,
        )
        design[condition] = (recipients[recipient_band], donors)
        stats[condition] = quality
    return design, stats


def run_swap(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    trials: list[Trial],
    design: dict[str, tuple[np.ndarray, np.ndarray]],
    donor_store: ActivationStore,
    cfg: RunConfig | None = None,
    layers: tuple[int, ...] | None = None,
    positions: tuple[str, ...] = ("PANL", "PANL+1", "CC"),
    progress=None,
) -> pd.DataFrame:
    """Transplant donor activations into recipients, one (layer, position) at a time (§7.4)."""
    cfg = cfg or loaded.config
    layers = layers or cfg.layers
    target_ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind, classes=cfg.sentiment.classes)
    if cfg.prompt_kind in ("categorical", "magistral"):
        # See exp1_steering.run_steering's identical fix.
        midpoints = np.array(
            [cfg.sentiment.class_midpoint[c] for c in cfg.sentiment.classes], dtype=float
        )
    else:
        midpoints = numeric_midpoints(cfg.prompt_kind)

    # One clean baseline per recipient set, computed with the batching the
    # intervention runs use (see interventions.compute_clean_logits).
    clean_by_condition = {}
    for condition, (recipients, _) in design.items():
        key = tuple(recipients.tolist())
        if key not in clean_by_condition:
            logits = compute_clean_logits(
                loaded, [rendered[i] for i in recipients], target_ids, cfg.batch_size
            )
            clean_by_condition[key] = (logits, logits.argmax(axis=1))

    frames = []
    grid = [(l, p, c) for l in layers for p in positions for c in design]
    iterator = progress(grid) if progress else grid
    for layer, position, condition in iterator:
        recipients, donors = design[condition]
        recipient_rendered = [rendered[i] for i in recipients]
        clean_logits, clean_index = clean_by_condition[tuple(recipients.tolist())]
        donor_acts = torch.tensor(donor_store.get(layer, position)[donors], dtype=torch.float32)

        def fn_factory(chunk, offset, position=position, donor_acts=donor_acts):
            return replace(
                [r.positions[position] for r in chunk], donor_acts[offset: offset + len(chunk)]
            )

        logits = run_with_intervention(
            loaded, recipient_rendered, layer, fn_factory, target_ids, cfg.batch_size
        )
        values = intervention_metrics(logits, clean_logits, clean_index, midpoints)
        frames.append(
            trial_frame(values, layer=layer, position=position, condition=condition)
        )
    return pd.concat(frames, ignore_index=True)


def cross_minus_same(summary: pd.DataFrame, metric: str = "confidence_change") -> pd.DataFrame:
    """Cross-confidence minus same-confidence effect — the critical comparison (§7.5)."""
    rows = []
    for (layer, position), group in summary.groupby(["layer", "position"]):
        lookup = group.set_index("condition")[f"{metric}_mean"].to_dict()
        rows.append(
            {
                "layer": layer,
                "position": position,
                "L->H minus L->L": lookup.get("L->H", np.nan) - lookup.get("L->L", np.nan),
                "H->L minus H->H": lookup.get("H->L", np.nan) - lookup.get("H->H", np.nan),
            }
        )
    return pd.DataFrame(rows).sort_values(["position", "layer"]).reset_index(drop=True)
