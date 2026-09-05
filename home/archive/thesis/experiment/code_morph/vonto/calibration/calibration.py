"""Calibration analysis — the actual (dataset, observation method, ground
truth) cross-product experiment (paper's Experiment 0), built on top of
`generation.generate_trial`/`observation.observe_trial`: sample seeds from a
`Dataset`, generate a `Trial` per seed (cached to disk — a real forward-pass-
per-token cost, unlike everything downstream of it), elicit every observation
method's self-report about each trial, grade every trial against every
ground truth, and correlate the two.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from tqdm.auto import tqdm

from ..dataset import Dataset, Inquiry, Trial
from ..ground_truth import GroundTruth
from ..observation_method import ObservationMethod
from .generation import generate_trial
from .observation import observe_trial


def _sample_seeds(dataset: Dataset, n_trials: int, rng_seed: int) -> list:
    """``n_trials`` seeds from ``dataset.seeds``, deterministic in
    ``rng_seed`` so a rerun (cache hit or not) samples exactly the same
    seeds — ``generate()``/``load_if_cached()`` is the caller's job, not
    this function's, since a dataset may already be loaded from elsewhere.
    """
    rng = np.random.default_rng(rng_seed)
    n = min(n_trials, len(dataset.seeds))
    indices = sorted(rng.choice(len(dataset.seeds), size=n, replace=False).tolist())
    return [dataset.seeds[i] for i in indices]


def _trial_to_record(t: Trial) -> dict:
    return {
        "inquiry": asdict(t.inquiry),
        "response": t.response,
        "answer_logprobs": t.answer_logprobs,
        "answer_entropies": t.answer_entropies,
    }


def _record_to_trial(seed, record: dict) -> Trial:
    return Trial(
        seed=seed,
        inquiry=Inquiry(**record["inquiry"]),
        response=record["response"],
        answer_logprobs=record["answer_logprobs"],
        answer_entropies=record["answer_entropies"],
    )


def generate_trials(
    loaded, dataset: Dataset, n_trials: int, cache_dir: str | Path, rng_seed: int = 0, sentiment_om=None,
) -> list[Trial]:
    """``n_trials`` seeds sampled from ``dataset``, each turned into a
    `Trial` (`generation.generate_trial`) — cached to
    ``<cache_dir>/<dataset.shape_tag()>_trials_n<n_trials>.json`` so a rerun
    loads the same generations back instead of regenerating them.
    ``sentiment_om``, when given, is passed straight through to
    `generation.generate_trial` (front-loading that OM's own instructions
    ahead of the question) — leave unset for a construct-agnostic Phase 0.
    """
    cache_dir = Path(cache_dir)
    path = cache_dir / f"{dataset.shape_tag()}_trials_n{n_trials}.json"
    seeds = _sample_seeds(dataset, n_trials, rng_seed)

    if path.exists():
        records = json.loads(path.read_text())
        return [_record_to_trial(seed, record) for seed, record in zip(seeds, records)]

    trials = [
        generate_trial(loaded, seed, dataset.inquiry(seed), sentiment_om=sentiment_om)
        for seed in tqdm(seeds, desc=f"{dataset.shape_tag()}: generating trials")
    ]

    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([_trial_to_record(t) for t in trials], indent=1))
    return trials


def generate_disjoint_pools(
    loaded, dataset: Dataset, n_extraction: int, n_test: int, cache_dir: str | Path, rng_seed: int = 0,
    sentiment_om=None,
) -> tuple[list[Trial], list[Trial]]:
    """Two disjoint trial pools drawn from ``dataset`` in one RNG draw —
    ``n_extraction`` trials to build a steering vector from, ``n_test``
    trials to measure its effect on — so a trial's own activation never
    partly builds the vector that is then used to steer it (reproduction
    guidebook §2.3.4: "steering vectors are extracted from the 3,000-trial
    activation set, and steering is tested on different questions"; §4.2).
    Cached separately per pool (``_extract_n<n_extraction>`` /
    ``_test_n<n_test>`` suffixes distinct from `generate_trials`' own
    ``_trials_n<n>`` tag), so a rerun loads the same split rather than
    re-drawing a different one. Raises if ``dataset`` doesn't have enough
    seeds for both pools at once — silently shrinking one pool would make
    "disjoint" meaningless. ``sentiment_om`` is passed straight through to
    `generation.generate_trial` for both pools — see `generate_trials`.
    """
    cache_dir = Path(cache_dir)
    rng = np.random.default_rng(rng_seed)
    total = n_extraction + n_test
    if len(dataset.seeds) < total:
        raise ValueError(
            f"{dataset.shape_tag()} has only {len(dataset.seeds)} seeds, need "
            f"{total} ({n_extraction} extraction + {n_test} test) for a disjoint split"
        )
    indices = rng.choice(len(dataset.seeds), size=total, replace=False)
    extract_idx = sorted(indices[:n_extraction].tolist())
    test_idx = sorted(indices[n_extraction:].tolist())

    extraction_seeds = [dataset.seeds[i] for i in extract_idx]
    test_seeds = [dataset.seeds[i] for i in test_idx]

    extraction_path = cache_dir / f"{dataset.shape_tag()}_trials_extract_n{n_extraction}.json"
    test_path = cache_dir / f"{dataset.shape_tag()}_trials_test_n{n_test}.json"

    def _load_or_generate(seeds, path, desc):
        if path.exists():
            records = json.loads(path.read_text())
            return [_record_to_trial(seed, record) for seed, record in zip(seeds, records)]
        trials = [
            generate_trial(loaded, seed, dataset.inquiry(seed), sentiment_om=sentiment_om)
            for seed in tqdm(seeds, desc=desc)
        ]
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([_trial_to_record(t) for t in trials], indent=1))
        return trials

    extraction_trials = _load_or_generate(
        extraction_seeds, extraction_path, f"{dataset.shape_tag()}: generating extraction trials"
    )
    test_trials = _load_or_generate(
        test_seeds, test_path, f"{dataset.shape_tag()}: generating test trials"
    )
    return extraction_trials, test_trials


def observe_all(
    loaded, trials: list[Trial], methods: list[ObservationMethod], cache_dir: str | Path, dataset_tag: str,
) -> dict[str, list]:
    """Elicit every method's self-report about every trial — cached per
    ``(dataset, method)`` pair (``<cache_dir>/<dataset_tag>_<method.name>_observed.json``),
    so a rerun skips the forward pass entirely. Returns ``{method.name:
    [(class, midpoint), ...]}``, one entry per trial, in trial order.
    """
    cache_dir = Path(cache_dir)
    observations: dict[str, list] = {}
    for method in tqdm(methods, desc=f"{dataset_tag}: observation methods"):
        path = cache_dir / f"{dataset_tag}_{method.name}_observed.json"
        if path.exists():
            observations[method.name] = json.loads(path.read_text())
            continue
        results = [
            list(observe_trial(loaded, trial, method).observed)
            for trial in tqdm(trials, desc=f"{dataset_tag}: {method.name} observations", leave=False)
        ]
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, indent=1))
        observations[method.name] = results
    return observations


def grade_all(
    trials: list[Trial], grounds: list[GroundTruth], cache_dir: str | Path, dataset_tag: str,
) -> dict[str, list[float]]:
    """Grade every trial against every ground truth — cached per
    ``(dataset, ground truth)`` pair (``<cache_dir>/<dataset_tag>_<gt.name>_values.json``).
    Returns ``{gt.name: [float, ...]}``, one value per trial, in trial order.
    """
    cache_dir = Path(cache_dir)
    grades: dict[str, list[float]] = {}
    for gt in tqdm(grounds, desc=f"{dataset_tag}: ground truths"):
        path = cache_dir / f"{dataset_tag}_{gt.name}_values.json"
        if path.exists():
            grades[gt.name] = json.loads(path.read_text())
            continue
        values = gt.values(trials)
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values, indent=1))
        grades[gt.name] = values
    return grades


def correlation_matrix(
    observations: dict[str, list], grades: dict[str, list[float]],
    oms: list[ObservationMethod], gts: list[GroundTruth],
) -> np.ndarray:
    """Spearman rho between every observation method's self-report midpoint
    and every ground truth's value, across the same trials — shape
    ``(len(oms), len(gts))``, row-major in ``oms``/``gts``' own given order."""
    matrix = np.zeros((len(oms), len(gts)))
    for i, om in enumerate(oms):
        midpoints = [midpoint for _, midpoint in observations[om.name]]
        for j, gt in enumerate(gts):
            rho, _ = spearmanr(midpoints, grades[gt.name])
            matrix[i, j] = rho
    return matrix


def run_calibration(
    loaded, dataset: Dataset, oms: list[ObservationMethod], gts: list[GroundTruth],
    cache_dir: str | Path, n_trials: int, rng_seed: int = 0,
) -> tuple[np.ndarray, list[Trial], dict[str, list], dict[str, list[float]]]:
    """The full cross-product experiment for one dataset: generate, observe,
    grade, correlate. Returns ``(matrix, trials, observations, grades)``."""
    trials = generate_trials(loaded, dataset, n_trials, cache_dir, rng_seed)
    observations = observe_all(loaded, trials, oms, cache_dir, dataset.shape_tag())
    grades = grade_all(trials, gts, cache_dir, dataset.shape_tag())
    matrix = correlation_matrix(observations, grades, oms, gts)
    return matrix, trials, observations, grades
