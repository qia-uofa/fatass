"""Tidy per-trial results and their aggregation (mean ± SEM, §2.8 (6))."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics as M

#: The metrics reported across the causal experiments.
TRIAL_METRICS = ("confidence_change", "logit_diff_change", "token_changed")


def trial_frame(values: dict[str, np.ndarray], **keys) -> pd.DataFrame:
    """One row per trial, tagged with the condition keys (layer, position, ...)."""
    frame = pd.DataFrame({name: np.asarray(value) for name, value in values.items()})
    for key, value in keys.items():
        frame[key] = value
    frame["trial"] = np.arange(len(frame))
    return frame


def summarize(
    frame: pd.DataFrame,
    by: list[str] | tuple[str, ...] = ("position", "condition", "layer"),
    metrics: list[str] | tuple[str, ...] = TRIAL_METRICS,
) -> pd.DataFrame:
    """Mean and SEM of each metric per condition — the paper's plotted quantities."""
    by = [column for column in by if column in frame.columns]
    rows = []
    for key, group in frame.groupby(list(by), dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(by, key))
        row["n"] = len(group)
        for metric in metrics:
            if metric not in group:
                continue
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_sem"] = M.sem(group[metric].to_numpy())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(by).reset_index(drop=True)


def peak_layer(summary: pd.DataFrame, metric: str, position: str, condition=None, mode="abs") -> int:
    """Layer at which a position's effect peaks — the paper's headline comparison."""
    frame = summary[summary["position"] == position]
    if condition is not None and "condition" in frame:
        frame = frame[frame["condition"] == condition]
    if frame.empty:
        return -1
    values = frame[f"{metric}_mean"]
    values = values.abs() if mode == "abs" else (values if mode == "max" else -values)
    return int(frame.loc[values.idxmax(), "layer"])


def compare_to_control(
    frame: pd.DataFrame,
    metric: str,
    position: str,
    control: str = "PANL+1",
    layer: int | None = None,
    condition: str | None = None,
) -> dict:
    """Paired test of a position against its control on matched trials (§13 #11)."""
    subset = frame
    if layer is not None:
        subset = subset[subset["layer"] == layer]
    if condition is not None and "condition" in subset:
        subset = subset[subset["condition"] == condition]
    a = subset[subset["position"] == position].sort_values("trial")[metric].to_numpy()
    b = subset[subset["position"] == control].sort_values("trial")[metric].to_numpy()
    size = min(len(a), len(b))
    return M.paired_comparison(a[:size], b[:size])
