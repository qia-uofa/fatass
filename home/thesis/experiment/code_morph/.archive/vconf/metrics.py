"""The metrics that recur throughout the paper (§2.8) — implemented once.

Everything here is pure NumPy so it can be unit-tested without a model.
Logits are always restricted to the K target tokens (the ten class-initial
tokens, or the ten digits for the numeric prompts), never the full
vocabulary — except `answer_set_entropy`, which deliberately needs the full
next-token distribution (see its docstring).
"""

from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

from .prompts import CLASSES, CLASS_MIDPOINT, PHASE0_KIND, build_phase0_prompt

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


def class_histogram(class_index: np.ndarray, classes: tuple[str, ...] = CLASSES) -> dict[str, int]:
    """Counts per sentiment class, in ``classes`` order."""
    idx = np.asarray(class_index, dtype=int)
    return {name: int((idx == i).sum()) for i, name in enumerate(classes)}


# --------------------------------------------------------------------------- #
# Intrinsic-ground-truth metrics (plan_benzon.md) — computed from the model's
# own generation, not an external fact.
# --------------------------------------------------------------------------- #


def mean_answer_logprob(trial) -> float:
    """Length-normalised mean log-probability of the trial's own answer tokens.

    `commitment`'s ground truth (plan_benzon.md Part 1) — reuses
    ``Trial.answer_logprobs``, already populated for every trial regardless
    of dataset. NaN for a trial with no recorded answer tokens.
    """
    logprobs = trial.answer_logprobs
    return float(np.mean(logprobs)) if logprobs else float("nan")


def intrinsic_correlation(class_midpoints: np.ndarray, raw_metric: np.ndarray) -> float:
    """Spearman rank correlation between a self-report's class midpoint and the
    raw continuous quantity an ``IntrinsicMetricThreshold`` ground truth
    thresholds boolean — a complement to the boolean-event ECE/AUROC pair,
    for reading a graded effect (e.g. Part 3's caveated-vs-clean-pairs
    comparison) that a median split alone would flatten. NaN pairs are
    dropped before computing the correlation; a self-report that collapsed to
    one class (zero variance) leaves rho undefined (``NaN``) — a real,
    reportable result, not a gap to paper over.
    """
    x = np.asarray(class_midpoints, dtype=float)
    y = np.asarray(raw_metric, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return float("nan")
    return float(stats.spearmanr(x[mask], y[mask]).correlation)


#: Appended only to `nuance`'s auxiliary resampling prompt (never the trial's
#: primary, already-logged Phase-0 answer) — keeps each of the N extra
#: generations short, which is both what makes resampling affordable and what
#: makes normalized-exact-match bucketing (rather than semantic clustering) a
#: legitimate way to estimate the answer distribution (plan_benzon.md).
NUANCE_ONE_WORD_SUFFIX = "\nAnswer with a single word."


def logit_entropy(logits) -> float:
    """Shannon entropy (nats) of the softmax distribution over one vocabulary-sized
    logits vector (a single generation step's full next-token distribution).

    Pure-tensor function, no model call — the part of `answer_set_entropy` that's
    directly unit-testable against a synthetic logits vector (one-hot -> 0,
    uniform over ``V`` entries -> ``log(V)``).
    """
    import torch

    log_probs = torch.log_softmax(logits.float(), dim=-1)
    return float(-(log_probs.exp() * log_probs).sum())


def answer_set_entropy(trial, loaded, cfg) -> float:
    """Shannon entropy (nats) of the model's next-token distribution when forced to
    answer in a single word (`nuance`'s ground truth, `plan_benzon.md` Part 1,
    revised again) — one forward pass' full-vocabulary softmax entropy at the
    answer position, not an empirical distribution over N resampled, decoded
    strings. ``loaded``/``cfg`` make this signature not fit
    ``IntrinsicMetricThreshold.metric_fn``'s bare ``Callable[[Trial], float]``
    directly; bind them with ``functools.partial`` at the point the run's
    ``RunConfig`` actually exists, not as a module-level constant (wrinkle #2).

    Supersedes the earlier "costly, faithful" design (bucket N independently
    resampled short answers by normalized exact match, `shannon_entropy_of_samples`
    in git history): TriviaQA's free-form phrasing meant paraphrases of the *same*
    fact ("J. G. Ballard" vs "James Graham Ballard") landed in different buckets,
    inflating entropy on exactly the items a faithful ground truth should call
    low-entropy — the resampling design's self-report correlation collapsed to
    rho=0.073 on TriviaQA despite passing cleanly (rho=0.421) on the
    ontology-trivials anchor, whose short, rigid expected answers don't have this
    problem (`notebooks_benzon/phase_0_calibration/2_nuance.ipynb`). Forcing a single-word answer
    collapses "which fact does the model believe" onto one token position by
    construction, so a single forward pass' full-vocabulary distribution *is* the
    answer distribution — no resampling, no bucketing, no surface-form artifact,
    and no extra generations (unlike the resampling design's N extra generations
    per trial, this is one forward pass, same cost as any other single-token
    logit read elsewhere in this codebase).

    Not the "cheap first-token proxy" `plan_benzon.md` open question #2 originally
    rejected in favor of resampling: that proxy read the first token of the
    *primary, open-ended* logged answer, which conflates formatting/stylistic
    branching (how the answer starts) with substantive answer branching (what the
    answer is). Forcing this *auxiliary* read itself to a single word removes that
    ambiguity instead of just accepting it for cheapness — there's effectively
    only one token position where "which fact" gets decided.
    """
    from .models import final_logits_of_texts, render_prompt  # deferred: torch-heavy

    kind = PHASE0_KIND[cfg.prompt_kind]
    built = build_phase0_prompt(
        trial.question, kind, sentiment=cfg.sentiment,
        strip_question_punctuation=cfg.strip_question_punctuation,
    )
    rendered = render_prompt(loaded.tokenizer, built, cfg.use_chat_template)
    logits = final_logits_of_texts(
        loaded.model, loaded.tokenizer, [rendered.text + NUANCE_ONE_WORD_SUFFIX]
    )[0]
    return logit_entropy(logits)


def nonbinary_mass(trial, loaded, cfg) -> float:
    """NBGT: total softmax probability mass on tokens OTHER than {Yes, No} at
    the Phase-0 answer position — ``1 - P(Yes) - P(No)`` over the *full*
    vocabulary softmax, not renormalized to just the pair. High = the model
    wants to say something other than a clean binary answer (a hedge, a
    qualification, a third option); near zero = confidently Yes-or-No.
    Reuses the exact Phase-0 prompt verbatim (no suffix, no generation), same
    cost shape as `answer_set_entropy`. Originally a `benzon:synonyms`-only
    helper (`notebooks_benzon/phase_0_calibration/3_synonyms.ipynb`); promoted here so the
    same NBGT computation is reusable as a general ground truth on any
    dataset, not just ones whose questions are already yes/no-shaped.
    """
    import torch

    from .models import final_logits_of_texts, render_prompt  # deferred: torch-heavy

    kind = PHASE0_KIND[cfg.prompt_kind]
    built = build_phase0_prompt(
        trial.question, kind, sentiment=cfg.sentiment,
        strip_question_punctuation=cfg.strip_question_punctuation,
    )
    rendered = render_prompt(loaded.tokenizer, built, cfg.use_chat_template)
    logits = final_logits_of_texts(loaded.model, loaded.tokenizer, [rendered.text])[0]
    yes_id = loaded.tokenizer(" Yes", add_special_tokens=False)["input_ids"][0]
    no_id = loaded.tokenizer(" No", add_special_tokens=False)["input_ids"][0]
    probs = torch.softmax(logits.float(), dim=-1)
    return float(1.0 - probs[yes_id] - probs[no_id])


def mean_pairwise_cosine_distance(vectors: list[np.ndarray]) -> float:
    """Mean pairwise cosine distance (``1 - cosine similarity``) over a set of
    vectors — `variety`'s ground truth (`activations.list_embedding_variety`,
    plan_benzon.md Part 4): the spread of a generated list's own items in the
    model's own embedding space. Fewer than two vectors have no pair to
    compare; returns ``NaN`` rather than ``0.0``, since "no variety" and
    "variety not computable" are different claims — a one-item list isn't
    maximally uniform, it's a case `IntrinsicMetricThreshold`'s NaN-safe
    median (`v == v`) already knows to drop.
    """
    if len(vectors) < 2:
        return float("nan")
    matrix = np.stack([np.asarray(v, dtype=float) for v in vectors])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized = matrix / np.clip(norms, 1e-12, None)
    similarity = normalized @ normalized.T
    i, j = np.triu_indices(len(vectors), k=1)
    return float((1.0 - similarity[i, j]).mean())


def gini_impurity(a: int, b: int) -> float:
    """Gini impurity of a binary split of sizes ``a``/``b`` — `impurity`'s
    ground truth (plan_benzon.md Part 5): how evenly a 20-Questions turn's
    question actually divided the remaining keywords into its
    (`twenty_questions.parse_partition`) yes/no partition. ``0.0`` for an
    all-one-side split (a useless question — eliminates nothing); ``0.5``,
    its maximum, for a perfectly even split (the best possible question, in
    the pure information-theoretic sense this metric captures).
    """
    total = a + b
    return 0.0 if total == 0 else 1 - (a / total) ** 2 - (b / total) ** 2


def binary_entropy(a: float, b: float) -> float:
    """Shannon entropy (bits) of a binary split of sizes ``a``/``b`` — same
    scale-invariant shape as `gini_impurity` (call with real percentages, not
    just integer counts): `labeled entropy` (`disagreement_gt`, `philpapers`)
    reuses this on the real survey ``agree_pct``/``disagree_pct`` split, a
    genuine entropy calculation rather than a Gini-impurity stand-in. ``0.0``
    for an all-one-side split (no real disagreement at all); ``1.0``, its
    maximum, for a perfectly even 50/50 split (maximum real-population
    disagreement).
    """
    total = a + b
    if total == 0:
        return 0.0
    p = a / total
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-p * np.log2(p) - (1 - p) * np.log2(1 - p))
