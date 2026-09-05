"""The metrics that recur throughout the paper (§2.8) — implemented once.

Everything here is pure NumPy so it can be unit-tested without a model.
Logits are always restricted to the K target tokens (the ten class-initial
tokens, or the ten digits for the numeric prompts), never the full vocabulary.
"""

from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

from .prompts import CLASSES, CLASS_MIDPOINT

#: Confidence midpoints in ``CLASSES`` order (§2.5.1).
MIDPOINTS = np.array([CLASS_MIDPOINT[name] for name in CLASSES], dtype=float)


def logit_difference(class_logits: np.ndarray, y: int | np.ndarray) -> np.ndarray:
    """Δ_logit = z_y − mean(z_k, k ≠ y) over the K target tokens (§2.8 (1)).

    ``class_logits`` is ``(K,)`` or ``(N, K)``; ``y`` is the class the *clean*
    run predicted and is held fixed across intervention conditions.
    """
    z = np.atleast_2d(np.asarray(class_logits, dtype=float))
    y_arr = np.atleast_1d(np.asarray(y, dtype=int))
    n, k = z.shape
    rows = np.arange(n)
    z_y = z[rows, y_arr]
    others = (z.sum(axis=1) - z_y) / (k - 1)
    out = z_y - others
    return out if np.ndim(class_logits) == 2 else out[0]


def logit_difference_change(
    intervened_logits: np.ndarray, clean_logits: np.ndarray, y: np.ndarray
) -> np.ndarray:
    """(intervened Δ_logit) − (clean Δ_logit), target class fixed at ``y`` (§2.8)."""
    return logit_difference(intervened_logits, y) - logit_difference(clean_logits, y)


def predicted_class(class_logits: np.ndarray) -> np.ndarray:
    """Argmax over the K target tokens."""
    return np.asarray(class_logits, dtype=float).argmax(axis=-1)


def confidence(class_index: np.ndarray, midpoints: np.ndarray | None = None) -> np.ndarray:
    """Confidence = midpoint of the predicted class's probability range (§2.8 (2))."""
    mids = MIDPOINTS if midpoints is None else np.asarray(midpoints, dtype=float)
    return mids[np.asarray(class_index, dtype=int)]


def confidence_change(
    intervened_index: np.ndarray, clean_index: np.ndarray, midpoints: np.ndarray | None = None
) -> np.ndarray:
    """Intervened confidence − clean confidence (§2.8 (2))."""
    return confidence(intervened_index, midpoints) - confidence(clean_index, midpoints)


def first_token_change_rate(intervened_index: np.ndarray, clean_index: np.ndarray) -> float:
    """Proportion of trials whose argmax confidence token differs from clean (§2.8 (3))."""
    a = np.asarray(intervened_index)
    b = np.asarray(clean_index)
    if a.size == 0:
        return float("nan")
    return float((a != b).mean())


def percent_recovery(patched: float, corrupt: float, clean: float) -> float:
    """(M_patched − M_corrupt) / (M_clean − M_corrupt) × 100 (§2.8 (4))."""
    denom = clean - corrupt
    if denom == 0:
        return float("nan")
    return float((patched - corrupt) / denom * 100.0)


def percent_recovery_change_rate(rate_patched: float, rate_corrupt: float) -> float:
    """Inverted recovery for the first-token change rate, where lower is better (§2.8 (4))."""
    if rate_corrupt == 0:
        return float("nan")
    return float((rate_corrupt - rate_patched) / rate_corrupt * 100.0)


def expected_calibration_error(
    confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> float:
    """ECE with equal-width bins, no temperature scaling (§2.8 (5), §13 #8)."""
    conf = np.asarray(confidences, dtype=float)
    acc = np.asarray(correct, dtype=float)
    if conf.size == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # np.digitize with right=False puts 1.0 in an extra bin; clip it back.
    idx = np.clip(np.digitize(conf, edges[1:-1], right=False), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        ece += mask.mean() * abs(acc[mask].mean() - conf[mask].mean())
    return float(ece)


def auroc(scores: np.ndarray, correct: np.ndarray) -> float:
    """AUROC for discriminating correct from incorrect answers (§2.8 (5))."""
    y = np.asarray(correct, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, np.asarray(scores, dtype=float)))


def sem(values: np.ndarray) -> float:
    """Standard error of the mean across trials — the paper's error bars (§2.8 (6))."""
    x = np.asarray(values, dtype=float)
    if x.size < 2:
        return float("nan")
    return float(x.std(ddof=1) / np.sqrt(x.size))


def mean_sem(values: np.ndarray) -> tuple[float, float]:
    x = np.asarray(values, dtype=float)
    return (float(x.mean()) if x.size else float("nan"), sem(x))


def non_overlapping(mean_a: float, sem_a: float, mean_b: float, sem_b: float) -> bool:
    """Whether two conditions' SEM bars are clearly non-overlapping (§2.8 (6))."""
    lo_a, hi_a = mean_a - sem_a, mean_a + sem_a
    lo_b, hi_b = mean_b - sem_b, mean_b + sem_b
    return hi_a < lo_b or hi_b < lo_a


def paired_comparison(condition: np.ndarray, control: np.ndarray) -> dict:
    """Paired t-test + Wilcoxon signed-rank + Cohen's d on matched trials (§13 #11)."""
    a = np.asarray(condition, dtype=float)
    b = np.asarray(control, dtype=float)
    diff = a - b
    out = {
        "n": int(a.size),
        "mean_condition": float(a.mean()) if a.size else float("nan"),
        "mean_control": float(b.mean()) if b.size else float("nan"),
        "mean_difference": float(diff.mean()) if diff.size else float("nan"),
        "sem_difference": sem(diff),
    }
    if a.size >= 2 and np.any(diff != 0):
        t_stat, t_p = stats.ttest_rel(a, b)
        out["t_stat"], out["t_p"] = float(t_stat), float(t_p)
        try:
            w_stat, w_p = stats.wilcoxon(a, b)
            out["wilcoxon_stat"], out["wilcoxon_p"] = float(w_stat), float(w_p)
        except ValueError:
            out["wilcoxon_stat"], out["wilcoxon_p"] = float("nan"), float("nan")
        out["cohens_d"] = float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) else float("nan")
    else:
        out.update(
            t_stat=float("nan"), t_p=float("nan"), wilcoxon_stat=float("nan"),
            wilcoxon_p=float("nan"), cohens_d=float("nan"),
        )
    return out


def class_histogram(class_index: np.ndarray) -> dict[str, int]:
    """Counts per confidence class, in ``CLASSES`` order."""
    idx = np.asarray(class_index, dtype=int)
    return {name: int((idx == i).sum()) for i, name in enumerate(CLASSES)}
