"""Experiment 0 — Behavioral baseline and calibration (§3).

Establishes that the model produces a meaningful, reasonably calibrated
confidence signal, and generates the Phase-0/Phase-1 records every later
experiment consumes.  This is a prerequisite, not an optional preliminary: if
calibration is far off, the prompt or the answer extraction is wrong (§3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import config as cfgmod
from . import grading
from . import metrics as M
from .config import RunConfig
from .data import QuestionItem
from .models import LoadedModel, sanity_check_forward_vs_generate, target_token_ids
from .pipeline import Trial, collect_trials, generate_numeric_confidence
from .positions import RenderedPrompt
from .prompts import CLASSES

#: Validation targets from §3.3 / §14.2.
PAPER_TARGETS: dict[str, dict[str, float | int | str]] = {
    "gemma-categorical": {"n": 7858, "accuracy": 0.774, "ece": 0.12, "auroc": 0.71},
    "gemma-numeric": {"n": 8008, "ece": 0.16, "auroc": 0.73},
    "gemma-minimal-numeric": {"n": 2000, "ece": 0.17, "auroc": 0.68},
    "qwen-categorical": {"ece": 0.06, "auroc": 0.65},
    "gemma-bigmath": {"accuracy": 0.402},
    "gemma-mmlu": {"accuracy": 0.768},
    "magistral-categorical": {"n": 4998, "almost_certain_share": 0.92},
}

#: Mean confidence of the intervention trial sets — the zero-point of the
#: confidence-change plots (§3.3).
BASELINE_CONFIDENCE = {
    "gemma-categorical-steering": 0.55,
    "gemma-categorical-figure22": 0.48,
    "gemma-numeric": 0.54,
    "qwen-categorical": 0.56,
}

#: §3.3 note: the length-normalised mean answer log-probability is a *better*
#: correctness predictor than the verbal report — the calibration gap that makes
#: the second-order question of §9 non-trivial.
LOGPROB_CORRECTNESS_AUROC = 0.75
VERBAL_CORRECTNESS_AUROC = 0.71


@dataclass
class BehavioralResult:
    """Everything §3.1 asks to be recorded for one behavioural run."""

    trials: list[Trial]
    rendered: list[RenderedPrompt] = field(default_factory=list)
    accuracy: float = float("nan")
    ece: float = float("nan")
    auroc: float = float("nan")
    histogram: dict[str, int] = field(default_factory=dict)
    hedging_rate: float = float("nan")
    baseline_confidence: float = float("nan")
    grader_name: str = ""
    sanity: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.trials)

    def summary(self) -> dict:
        return {
            "n": self.n,
            "accuracy": self.accuracy,
            "ece": self.ece,
            "auroc": self.auroc,
            "baseline_confidence": self.baseline_confidence,
            "hedging_rate": self.hedging_rate,
            "grader": self.grader_name,
        }


def calibration(trials: list[Trial], n_bins: int = cfgmod.ECE_BINS) -> dict[str, float]:
    """Accuracy, ECE (10 bins, no temperature scaling) and AUROC (§2.8 (5), §3.1)."""
    confidence = np.array([t.confidence for t in trials], dtype=float)
    correct = np.array([bool(t.correct) for t in trials], dtype=int)
    return {
        "accuracy": float(correct.mean()) if len(correct) else float("nan"),
        "ece": M.expected_calibration_error(confidence, correct, n_bins=n_bins),
        "auroc": M.auroc(confidence, correct),
        "baseline_confidence": float(confidence.mean()) if len(confidence) else float("nan"),
    }


def run_experiment0(
    loaded: LoadedModel,
    items: list[QuestionItem],
    cfg: RunConfig | None = None,
    target_n: int | None = None,
    grader=None,
    hedging_checker=None,
    sanity_n: int = 32,
    progress=None,
) -> BehavioralResult:
    """The full §3.1 procedure for one (model, prompt, dataset) setting."""
    cfg = cfg or loaded.config
    target_n = target_n or cfg.behavioral_n

    trials, rendered = collect_trials(loaded, items, cfg, target_n=target_n, progress=progress)
    if cfg.prompt_kind in ("numeric", "minimal_numeric"):
        # The stated confidence is the generated integer, not the first digit (§2.8).
        generate_numeric_confidence(loaded, trials, cfg)
        keep = [i for i, t in enumerate(trials) if t.confidence is not None]
        trials = [trials[i] for i in keep]
        rendered = [rendered[i] for i in keep]

    # §2.2 mandatory sanity check, on a held-out sample of the run.
    target_ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind, classes=cfg.sentiment.classes)
    sanity = sanity_check_forward_vs_generate(loaded, rendered[:sanity_n], target_ids)

    if grader is not None:
        # Explicit override: bypass cfg.ground_truth entirely (§2.3.1's raw
        # correctness grader), kept for callers that want the manual's
        # original grading path regardless of what ground truth cfg carries.
        correct = grading.grade_answers(
            [t.question for t in trials],
            [t.answer for t in trials],
            [t.gold_answers for t in trials],
            grader=grader,
        )
        grader_name = getattr(grader, "__name__", str(grader))
    else:
        ground_truth_items = [
            QuestionItem(qid=t.qid, question=t.question, answers=t.gold_answers) for t in trials
        ]
        correct = cfg.ground_truth.labels(ground_truth_items, trials)
        grader_name = getattr(cfg.ground_truth, "grader_name", cfg.ground_truth.name)
    for trial, is_correct in zip(trials, correct):
        trial.correct = bool(is_correct)

    stats = calibration(trials)
    hedging = grading.hedging_rate([t.answer for t in trials], checker=hedging_checker)
    histogram = M.class_histogram(
        np.array([t.class_index for t in trials], dtype=int), classes=cfg.sentiment.classes
    )
    if cfg.prompt_kind in ("numeric", "minimal_numeric"):
        histogram = {str(k): v for k, v in histogram.items()}
    return BehavioralResult(
        trials=trials,
        rendered=rendered,
        histogram=histogram,
        hedging_rate=hedging,
        grader_name=grader_name,
        sanity=sanity,
        **stats,
    )


def logprob_correctness_auroc(trials: list[Trial]) -> float:
    """AUROC of the length-normalised mean answer log-probability (§3.3 note)."""
    scores = np.array(
        [np.mean(t.answer_logprobs) if t.answer_logprobs else np.nan for t in trials]
    )
    correct = np.array([bool(t.correct) for t in trials], dtype=int)
    keep = ~np.isnan(scores)
    return M.auroc(scores[keep], correct[keep])


def class_distribution(trials: list[Trial], classes: tuple[str, ...] = CLASSES) -> dict[str, float]:
    """Share of trials in each sentiment class (§3.3 "Distribution")."""
    counts = M.class_histogram(np.array([t.class_index for t in trials], dtype=int), classes=classes)
    total = max(1, sum(counts.values()))
    return {name: counts[name] / total for name in classes}


def validate(result: BehavioralResult, target_key: str, tolerance: float = 0.05) -> dict:
    """Compare a run against the §3.3 targets, per quantity."""
    targets = PAPER_TARGETS.get(target_key, {})
    summary = result.summary()
    out = {}
    for key, target in targets.items():
        if key in ("n",) or key not in summary:
            continue
        observed = summary[key]
        out[key] = {
            "observed": observed,
            "paper": target,
            "within_tolerance": bool(abs(observed - target) <= tolerance)
            if observed == observed
            else False,
        }
    return out
