"""Experiment 6 — Linear probing and variance partitioning (§9).

Probing shows *where* confidence information first becomes decodable; variance
partitioning shows whether PANL representations merely summarise token
log-probabilities.  Both use 5-fold cross-validation with z-scored features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as cfgmod
from .activations import ActivationStore
from .pipeline import Trial

#: The six log-probability summaries of the answer span (§9.2).
BASELINE_NAMES = ("mean", "min", "max", "var", "first", "last")

#: §9.5 — decodability and the variance-partitioning headline numbers.
PAPER_TARGETS = {
    "probing": {
        "PANL": {"auroc": (0.80, 0.83), "r2": 0.45},
        "CC": {"auroc": (0.80, 0.83), "r2": 0.80},
        "PANL+1": {"auroc": 0.80, "r2": (0.35, 0.45)},
        "FCC": {"auroc": 0.80, "r2": 0.45},
        "QTT": {"auroc": 0.50, "r2": 0.00},
        "AC": {"r2": 0.2},
    },
    "reference_auroc": {"verbal_confidence": 0.71, "mean_logprob": 0.75},
    "baseline_r2": {
        "min": 0.101, "mean": 0.084, "first": 0.070, "var": 0.051, "last": 0.039,
        "max": 0.025, "all_six": 0.100,
    },
    "unique_r2_panl_l40": 0.380,
    "correlations": {
        "cross_run_r": 0.29, "cross_run_r2": 0.084,
        "within_run_r": 0.23, "within_run_r2": 0.049,
        "all_six_r": 0.32, "all_six_r2": 0.100,
        "phase0_phase1_r": 0.63, "phase0_phase1_r2": 0.40,
    },
}


def logprob_baselines(logprobs: list[float]) -> dict[str, float]:
    """The six summaries of the answer span's per-token log-probabilities (§9.2)."""
    values = np.asarray(logprobs, dtype=float)
    if values.size == 0:
        return {name: np.nan for name in BASELINE_NAMES}
    return {
        "mean": float(values.mean()),  # length-normalised mean
        "min": float(values.min()),
        "max": float(values.max()),
        "var": float(values.var()),
        "first": float(values[0]),
        "last": float(values[-1]),
    }


def baseline_matrix(trials: list[Trial]) -> tuple[np.ndarray, tuple[str, ...]]:
    """``(n, 6)`` matrix of log-probability baselines, in ``BASELINE_NAMES`` order."""
    rows = [logprob_baselines(t.answer_logprobs) for t in trials]
    matrix = np.array([[row[name] for name in BASELINE_NAMES] for row in rows], dtype=float)
    return matrix, BASELINE_NAMES


def _kfold(seed: int = cfgmod.SEED, n_splits: int = cfgmod.PROBE_FOLDS) -> KFold:
    return KFold(n_splits=n_splits, shuffle=True, random_state=seed)


def probe_correctness(X: np.ndarray, y: np.ndarray, seed: int = cfgmod.SEED) -> float:
    """Cross-validated AUROC of an L2-regularised logistic probe (§9.1, §13 #7)."""
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    # L2 is scikit-learn's default penalty; C is the §13 #7 default.
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=cfgmod.LOGREG_C, max_iter=2000))
    proba = cross_val_predict(clf, X, y, cv=_kfold(seed), method="predict_proba")[:, 1]
    return float(roc_auc_score(y, proba))


def probe_confidence(
    X: np.ndarray, y: np.ndarray, alpha: float = cfgmod.RIDGE_ALPHA, seed: int = cfgmod.SEED
) -> float:
    """Cross-validated R² of a Ridge probe for the confidence midpoint (§9.1)."""
    y = np.asarray(y, dtype=float)
    reg = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    pred = cross_val_predict(reg, X, y, cv=_kfold(seed))
    return float(r2_score(y, pred))


def layerwise_probing(
    store: ActivationStore,
    trials: list[Trial],
    positions: tuple[str, ...] | None = None,
    layers: tuple[int, ...] | None = None,
    alpha: float = cfgmod.RIDGE_ALPHA,
    seed: int = cfgmod.SEED,
    progress=None,
) -> pd.DataFrame:
    """AUROC (correctness) and R² (confidence midpoint) per (layer, position) (§9.1)."""
    positions = positions or store.positions
    layers = layers or store.layers
    y_correct = np.array([bool(t.correct) for t in trials], dtype=int)
    y_confidence = np.array([t.confidence for t in trials], dtype=float)
    rows = []
    grid = [(layer, position) for layer in layers for position in positions]
    iterator = progress(grid) if progress else grid
    for layer, position in iterator:
        X = store.get(layer, position)
        rows.append(
            {
                "layer": layer,
                "position": position,
                "correctness_auroc": probe_correctness(X, y_correct, seed=seed),
                "confidence_r2": probe_confidence(X, y_confidence, alpha=alpha, seed=seed),
            }
        )
    return pd.DataFrame(rows)


def variance_partition(
    X_activations: np.ndarray,
    X_baselines: np.ndarray,
    y: np.ndarray,
    alpha: float = cfgmod.RIDGE_ALPHA,
    seed: int = cfgmod.SEED,
) -> dict[str, float]:
    """R²_act, R²_base, R²_both and R²_unique = max(0, R²_both − R²_base) (§9.3)."""
    r2_act = probe_confidence(X_activations, y, alpha=alpha, seed=seed)
    r2_base = probe_confidence(X_baselines, y, alpha=alpha, seed=seed)
    r2_both = probe_confidence(
        np.concatenate([X_activations, X_baselines], axis=1), y, alpha=alpha, seed=seed
    )
    return {
        "r2_activations": r2_act,
        "r2_baselines": r2_base,
        "r2_both": r2_both,
        "r2_unique": float(max(0.0, r2_both - r2_base)),
    }


def layerwise_variance_partition(
    store: ActivationStore,
    trials: list[Trial],
    positions: tuple[str, ...] | None = None,
    layers: tuple[int, ...] | None = None,
    baseline: str = "all",
    alpha: float = cfgmod.RIDGE_ALPHA,
    seed: int = cfgmod.SEED,
    progress=None,
) -> pd.DataFrame:
    """Variance partitioning per (layer, position) (§9.3).

    ``baseline`` is ``"all"`` (all six combined — the most conservative test) or
    one of :data:`BASELINE_NAMES`.
    """
    positions = positions or store.positions
    layers = layers or store.layers
    matrix, names = baseline_matrix(trials)
    columns = list(range(len(names))) if baseline == "all" else [names.index(baseline)]
    X_base = matrix[:, columns]
    y = np.array([t.confidence for t in trials], dtype=float)
    keep = ~np.isnan(X_base).any(axis=1) & ~np.isnan(y)
    rows = []
    grid = [(layer, position) for layer in layers for position in positions]
    iterator = progress(grid) if progress else grid
    for layer, position in iterator:
        X_act = store.get(layer, position)[keep]
        result = variance_partition(X_act, X_base[keep], y[keep], alpha=alpha, seed=seed)
        rows.append({"layer": layer, "position": position, "baseline": baseline, **result})
    return pd.DataFrame(rows)


def baseline_only_r2(
    trials: list[Trial], alpha: float = cfgmod.RIDGE_ALPHA, seed: int = cfgmod.SEED
) -> pd.DataFrame:
    """R²_CV of each log-probability baseline alone, and of all six combined (§9.5)."""
    matrix, names = baseline_matrix(trials)
    y = np.array([t.confidence for t in trials], dtype=float)
    keep = ~np.isnan(matrix).any(axis=1) & ~np.isnan(y)
    rows = []
    for i, name in enumerate(names):
        column = matrix[keep][:, i]
        constant = np.ptp(column) == 0 or np.ptp(y[keep]) == 0
        rows.append(
            {
                "baseline": name,
                "r2_cv": probe_confidence(matrix[keep][:, [i]], y[keep], alpha=alpha, seed=seed),
                "pearson_r": float("nan") if constant
                else float(stats.pearsonr(column, y[keep])[0]),
            }
        )
    rows.append(
        {
            "baseline": "all six combined",
            "r2_cv": probe_confidence(matrix[keep], y[keep], alpha=alpha, seed=seed),
            "pearson_r": float("nan"),
        }
    )
    return pd.DataFrame(rows)


def correlation_diagnostics(trials: list[Trial]) -> dict[str, float]:
    """Scalar sanity checks of §9.4.

    Length-normalised answer log-probability against Phase-0 (within-run) and
    Phase-1 (cross-run) verbal confidence, plus the Phase-0/Phase-1 stability.
    """
    mean_logprob = np.array(
        [np.mean(t.answer_logprobs) if t.answer_logprobs else np.nan for t in trials]
    )
    phase1 = np.array([t.confidence for t in trials], dtype=float)
    phase0 = np.array(
        [t.phase0_confidence if t.phase0_confidence is not None else np.nan for t in trials]
    )
    out: dict[str, float] = {}

    def _corr(a, b, prefix):
        keep = ~np.isnan(a) & ~np.isnan(b)
        if keep.sum() < 3 or np.std(a[keep]) == 0 or np.std(b[keep]) == 0:
            out[f"{prefix}_r"] = float("nan")
            out[f"{prefix}_n"] = int(keep.sum())
            return
        out[f"{prefix}_r"] = float(stats.pearsonr(a[keep], b[keep])[0])
        out[f"{prefix}_n"] = int(keep.sum())

    _corr(mean_logprob, phase1, "logprob_vs_phase1")
    _corr(mean_logprob, phase0, "logprob_vs_phase0")
    _corr(phase0, phase1, "phase0_vs_phase1")
    return out
