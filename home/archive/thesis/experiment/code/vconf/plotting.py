"""Figures for the notebooks: layer curves with SEM error bars (§2.8 (6)).

Every plot draws the mean across trials with SEM error bars, which is the
paper's convention, and can overlay the paper's reported value so a run can be
read against its validation target directly.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as cfgmod
from . import metrics as M
from .prompts import CLASSES

POSITION_COLORS = {
    "PANL": "#1f77b4",
    "PANL+1": "#7f7f7f",
    "CC": "#d62728",
    "FCC": "#9467bd",
    "AC": "#2ca02c",
    "first A": "#8c564b",
    "last A": "#e377c2",
    "QTT": "#bcbd22",
}


def save_figure(fig, name: str, directory: Path | None = None) -> Path:
    directory = Path(directory or cfgmod.FIGURES_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path


def layer_curve(
    summary: pd.DataFrame,
    metric: str,
    ax=None,
    hue: str = "condition",
    title: str | None = None,
    ylabel: str | None = None,
    paper_value: float | None = None,
    paper_layers: tuple[int, int] | None = None,
):
    """Mean ± SEM of ``metric`` against layer, one line per ``hue`` level."""
    if ax is None:
        _, ax = plt.subplots(figsize=(5, 3.2))
    mean_col, sem_col = f"{metric}_mean", f"{metric}_sem"
    for level, group in summary.groupby(hue, dropna=False):
        group = group.sort_values("layer")
        ax.errorbar(
            group["layer"], group[mean_col], yerr=group[sem_col],
            marker="o", markersize=3, capsize=2, linewidth=1.4, label=str(level),
        )
    if paper_layers is not None:
        ax.axvspan(paper_layers[0], paper_layers[1], color="#ffd54f", alpha=0.25,
                   label=f"paper peak L{paper_layers[0]}–{paper_layers[1]}")
    if paper_value is not None:
        ax.axhline(paper_value, color="k", linestyle=":", linewidth=1,
                   label=f"paper ≈ {paper_value:g}")
    ax.axhline(0, color="k", linewidth=0.6, alpha=0.4)
    ax.set_xlabel("layer")
    ax.set_ylabel(ylabel or metric.replace("_", " "))
    if title:
        ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    return ax


def position_panels(
    summary: pd.DataFrame,
    metric: str,
    positions: tuple[str, ...],
    hue: str = "condition",
    ylabel: str | None = None,
    paper: dict | None = None,
    suptitle: str | None = None,
):
    """One panel per token position — the layout of the paper's main figures."""
    positions = [p for p in positions if p in set(summary["position"])]
    fig, axes = plt.subplots(1, len(positions), figsize=(4.2 * len(positions), 3.4), squeeze=False)
    shared = axes[0]
    for ax, position in zip(shared, positions):
        subset = summary[summary["position"] == position]
        target = (paper or {}).get(position, {}) if paper else {}
        layer_curve(
            subset, metric, ax=ax, hue=hue, title=position, ylabel=ylabel,
            paper_layers=target.get("peak_layers"),
        )
    lows = [ax.get_ylim()[0] for ax in shared]
    highs = [ax.get_ylim()[1] for ax in shared]
    for ax in shared:
        ax.set_ylim(min(lows), max(highs))
    if suptitle:
        fig.suptitle(suptitle, fontsize=11)
    fig.tight_layout()
    return fig


def reliability_diagram(confidences, correct, n_bins: int = 10, ax=None, title: str | None = None):
    """Stated confidence against empirical accuracy, with the ECE annotated (§2.8 (5))."""
    if ax is None:
        _, ax = plt.subplots(figsize=(4, 3.6))
    conf = np.asarray(confidences, dtype=float)
    acc = np.asarray(correct, dtype=float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1]), 0, n_bins - 1)
    centers, accuracies, counts = [], [], []
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        centers.append(conf[mask].mean())
        accuracies.append(acc[mask].mean())
        counts.append(int(mask.sum()))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="perfect calibration")
    ax.plot(centers, accuracies, "o-", color="#1f77b4", label="observed")
    for x, y, n in zip(centers, accuracies, counts):
        ax.annotate(str(n), (x, y), fontsize=6, xytext=(0, 5), textcoords="offset points")
    ece = M.expected_calibration_error(conf, acc, n_bins=n_bins)
    ax.set_xlabel("stated confidence")
    ax.set_ylabel("empirical accuracy")
    ax.set_title(f"{title or 'Calibration'} (ECE = {ece:.3f})", fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    return ax


def class_distribution_plot(class_index, ax=None, title: str | None = None, labels=None):
    """Histogram of predicted confidence classes (§3.1 item 6)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(5.5, 3))
    labels = labels or list(CLASSES)
    counts = np.bincount(np.asarray(class_index, dtype=int), minlength=len(labels))
    ax.bar(range(len(labels)), counts[: len(labels)], color="#1f77b4")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("trials")
    if title:
        ax.set_title(title, fontsize=10)
    return ax


def condition_bars(
    summary: pd.DataFrame,
    metric: str,
    layer: int,
    position: str = "PANL",
    paper: dict | None = None,
    ax=None,
    ylabel: str | None = None,
):
    """Bar chart of conditions at one layer, with the paper's values overlaid."""
    if ax is None:
        _, ax = plt.subplots(figsize=(5, 3.2))
    subset = summary[(summary["layer"] == layer) & (summary["position"] == position)]
    subset = subset.sort_values("condition")
    x = np.arange(len(subset))
    ax.bar(x, subset[f"{metric}_mean"], yerr=subset[f"{metric}_sem"], capsize=3,
           color="#1f77b4", label="reproduction")
    if paper:
        key = metric.replace("_mean", "")
        values = [paper.get(c, {}).get(key, np.nan) for c in subset["condition"]]
        ax.plot(x, values, "k_", markersize=18, label="paper")
    ax.set_xticks(x)
    ax.set_xticklabels(subset["condition"], rotation=30, ha="right", fontsize=8)
    ax.axhline(0, color="k", linewidth=0.6, alpha=0.4)
    ax.set_ylabel(ylabel or metric.replace("_", " "))
    ax.set_title(f"{position}, layer {layer}", fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    return ax


def probing_curves(frame: pd.DataFrame, metric: str, ax=None, reference: dict | None = None,
                   title: str | None = None):
    """Layerwise probing curves, one line per position (§9.5)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(5.5, 3.4))
    for position, group in frame.groupby("position"):
        group = group.sort_values("layer")
        ax.plot(group["layer"], group[metric], marker="o", markersize=3,
                color=POSITION_COLORS.get(str(position)), label=str(position))
    for name, value in (reference or {}).items():
        ax.axhline(value, linestyle=":", linewidth=1, color="k")
        ax.annotate(f"{name} = {value:g}", (ax.get_xlim()[0], value), fontsize=6,
                    xytext=(2, 2), textcoords="offset points")
    ax.set_xlabel("layer")
    ax.set_ylabel(metric.replace("_", " "))
    if title:
        ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    return ax


def comparison_table(observed: dict, paper: dict, name: str = "quantity") -> pd.DataFrame:
    """Side-by-side table of reproduced values against the paper's targets."""
    rows = []
    for key, target in paper.items():
        if not isinstance(target, (int, float)):
            continue
        value = observed.get(key, np.nan)
        rows.append(
            {
                name: key,
                "reproduction": value,
                "paper": target,
                "difference": (value - target) if isinstance(value, (int, float)) else np.nan,
            }
        )
    return pd.DataFrame(rows)
