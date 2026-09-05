"""Helpers the per-experiment notebooks share: run profiles and cached trials.

The manual's own settings (Gemma 3 27B, 7,858-question behavioural run, 3,000
activation trials, the full 22-layer sweep) are the ``"paper"`` profile.  The
``"reduced"`` profile keeps every procedure, prompt, position and metric
identical and only shrinks *how much* is run — model, trial counts, layer sweep
— so the notebooks execute end-to-end on one GPU.  Which profile a notebook
uses is printed at the top of every run, and the reduced numbers are never
presented as reproductions of the paper's numbers.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path

from . import config as cfgmod
from . import data as datamod
from .config import RunConfig, preset
from .models import LoadedModel, load_model
from .pipeline import Trial, collect_trials, load_trials, render_phase1, save_trials

#: Environment variables that select what a notebook runs.
PROFILE_ENV = "VCONF_PROFILE"  # "reduced" (default) | "paper"
MODEL_ENV = "VCONF_MODEL"  # a key of vconf.config.MODELS

TRIALS_DIR = cfgmod.RESULTS_DIR / "trials"

#: Phase-0 questions drawn per usable trial, at any profile: a generation is
#: discarded when its answer cannot be mapped back onto the generated tokens or
#: when the tokenizer merges the post-answer newline (§2.6).
POOL_MULTIPLIER = 6

#: The reduced profile's sizes.  Structure identical to the manual's; scale not.
REDUCED = {
    "activation_n": 300,
    "calibration_n": 40,
    # Large enough that the activation-collection set, the calibration set and
    # the per-experiment test sets can all be disjoint (§2.3.4).
    "behavioral_n": 1000,
    "trial_counts": {"steering": 24, "patching": 24, "noising": 32, "swap": 24,
                     "attention": 24},
    "batch_size": 8,
    "layer_count": 6,
    "attention_sweep_count": 4,
}


def profile() -> str:
    return os.environ.get(PROFILE_ENV, "reduced").lower()


def model_key(default: str | None = None) -> str:
    return os.environ.get(MODEL_ENV, default or ("qwen" if profile() == "reduced" else "gemma"))


def reduce_layers(layers: tuple[int, ...], count: int) -> tuple[int, ...]:
    """Keep ``count`` evenly spaced layers of a sweep, always including its ends."""
    if len(layers) <= count:
        return layers
    step = (len(layers) - 1) / (count - 1)
    picked = sorted({layers[round(i * step)] for i in range(count)})
    return tuple(picked)


def run_config(base: str | RunConfig = "gemma-categorical", **overrides) -> RunConfig:
    """The :class:`RunConfig` for a notebook, honouring the profile environment.

    Under the ``"paper"`` profile this is exactly the manual's preset; under
    ``"reduced"`` the model, trial counts and layer sweep are scaled down while
    prompts, positions, metrics and procedures are untouched.
    """
    cfg = preset(base) if isinstance(base, str) else base
    if profile() == "paper":
        return cfg.scaled(**overrides) if overrides else cfg

    key = model_key()
    cfg = cfg.scaled(
        model_key=key,
        layers=reduce_layers(cfgmod.LAYER_SWEEPS[key], REDUCED["layer_count"]),
        activation_n=REDUCED["activation_n"],
        calibration_n=REDUCED["calibration_n"],
        behavioral_n=REDUCED["behavioral_n"],
        trial_counts=REDUCED["trial_counts"],
        batch_size=REDUCED["batch_size"],
        attention_sweep=reduce_layers(
            tuple(c for c in cfgmod.ATTENTION_SWEEP if c < cfgmod.MODELS[key].n_layers),
            REDUCED["attention_sweep_count"],
        ),
        name=f"{key}-{cfg.prompt_kind}-{cfg.dataset}-reduced",
    )
    return cfg.scaled(**overrides) if overrides else cfg


def describe(cfg: RunConfig) -> str:
    """A one-paragraph banner describing what this notebook is about to run."""
    lines = [
        f"profile          : {profile()}",
        f"model            : {cfg.checkpoint} ({cfg.n_layers} layers)",
        f"sentiment        : {cfg.sentiment.name}  (ground truth: {cfg.ground_truth.name})",
        f"prompt / dataset : {cfg.prompt_kind} / {cfg.dataset}",
        f"layer sweep      : {cfg.layers}",
        f"trial counts     : {cfg.trial_counts}",
        f"activation set   : {cfg.activation_n}   calibration set: {cfg.calibration_n}",
        f"chat template    : {cfg.use_chat_template}   attention impl: {cfg.attn_implementation}",
    ]
    if profile() != "paper":
        lines.append(
            "NOTE             : reduced profile — procedures, prompts, positions and\n"
            "                   metrics follow the manual exactly, but the model and the\n"
            "                   sample sizes are smaller than the paper's, so the numbers\n"
            "                   here are not expected to match its reported values."
        )
    return "\n".join(lines)


def open_model(cfg: RunConfig, device_map: str | None = None) -> LoadedModel:
    """Load the checkpoint this run needs, on the GPU."""
    return load_model(cfg, device_map=device_map)


def trial_cache_path(cfg: RunConfig, target_n: int) -> Path:
    name = f"{cfg.model_key}-{cfg.prompt_kind}-{cfg.dataset}-n{target_n}"
    name += "-chat" if cfg.use_chat_template else "-raw"
    return TRIALS_DIR / f"{name}.json"


def build_trials(
    loaded: LoadedModel,
    cfg: RunConfig,
    target_n: int | None = None,
    pool: int | None = None,
    use_cache: bool = True,
    progress=None,
) -> tuple[list[Trial], list]:
    """Phase 0 + Phase 1 for ``target_n`` usable trials, cached on disk.

    A Phase-0 generation is discarded when the answer cannot be mapped back onto
    the generated tokens or when the tokenizer merges the post-answer newline
    with the answer's last token (§2.6), so more questions are drawn than trials
    are wanted.
    """
    target_n = target_n or cfg.behavioral_n
    pool = pool or target_n * POOL_MULTIPLIER
    path = trial_cache_path(cfg, target_n)
    if use_cache and path.exists():
        trials = load_trials(path)
    else:
        items = datamod.load_dataset_items(cfg.dataset)
        trials, _ = collect_trials(loaded, items[:pool], cfg, target_n=target_n, progress=progress)
        save_trials(trials, path)
    rendered = [render_phase1(loaded, trial, cfg) for trial in trials]
    return trials, rendered


def rendered_for(loaded: LoadedModel, trials: list[Trial], cfg: RunConfig) -> list:
    return [render_phase1(loaded, trial, cfg) for trial in trials]


def graded(trials: list[Trial], grader=None, ground_truth=None) -> list[Trial]:
    """Attach cached ground-truth labels to trials (§2.3.1).

    ``grader`` overrides the raw correctness-grading function directly (the
    manual's own §2.3.1 path); ``ground_truth`` overrides what ground truth is
    checked at all (a :mod:`vconf.ground_truth` object). With neither given,
    this reproduces today's default exactly: correctness against gold
    aliases, GPT-4o-mini when available.
    """
    from . import grading
    from .data import QuestionItem
    from .ground_truth import AliasCorrectness

    if grader is not None:
        labels = grading.grade_answers(
            [t.question for t in trials], [t.answer for t in trials],
            [t.gold_answers for t in trials], grader=grader,
        )
    else:
        ground_truth = ground_truth or AliasCorrectness()
        items = [QuestionItem(qid=t.qid, question=t.question, answers=t.gold_answers) for t in trials]
        labels = ground_truth.labels(items, trials)
    for trial, label in zip(trials, labels):
        trial.correct = bool(label)
    return trials


def grader_note() -> str:
    """One line stating which grader produced the correctness labels."""
    from . import grading

    if grading.openai_available():
        return "correctness graded by gpt-4o-mini (temperature 0), as the manual specifies (§2.3.1)"
    return (
        "OPENAI_API_KEY is not set, so correctness labels come from the documented "
        "fallback (normalised alias matching), not the manual's gpt-4o-mini grader "
        "(§2.3.1) — accuracy/ECE/AUROC here are approximate for that reason"
    )


def subset(trials: list[Trial], rendered: list, index) -> tuple[list[Trial], list]:
    """Index a trial list and its rendered prompts together."""
    return [trials[i] for i in index], [rendered[i] for i in index]


#: Positions cached for every activation-based analysis (§2.6).
STORE_POSITIONS = ("PANL", "PANL+1", "CC", "FCC", "AC", "first A", "last A", "QTT")


def activation_store(
    loaded: LoadedModel,
    cfg: RunConfig,
    rendered: list,
    positions: tuple[str, ...] = STORE_POSITIONS,
    layers: tuple[int, ...] | None = None,
    trials: list[Trial] | None = None,
    use_cache: bool = True,
    progress=None,
):
    """The activation-collection set's residual streams, cached on disk (§2.10)."""
    from .activations import ActivationStore, activation_path, collect_activations

    layers = layers or cfg.layers
    # The cache key has to identify *which* trials were collected, not just how
    # many: two runs can hold 300 trials each and share not one question.
    identity = "|".join(t.qid for t in trials) if trials else "|".join(r.text for r in rendered)
    digest = hashlib.sha1(identity.encode()).hexdigest()[:10]
    name = f"{cfg.name}-n{len(rendered)}-{digest}-l{len(layers)}-p{len(positions)}"
    path = activation_path(name)
    if use_cache and path.exists():
        store = ActivationStore.load(path)
        if store.layers == tuple(layers) and store.positions == tuple(positions):
            return store
    store = collect_activations(
        loaded, rendered, layers, positions,
        trial_ids=[t.qid for t in trials] if trials else None,
        batch_size=cfg.batch_size, progress=progress,
    )
    store.save(path)
    return store


# --------------------------------------------------------------------------- #
# The disjoint partition (§2.3.4)
# --------------------------------------------------------------------------- #


def split_activation_holdout(
    trials: list[Trial], rendered: list, cfg: RunConfig, seed: int | None = None
) -> tuple[tuple[list[Trial], list], tuple[list[Trial], list]]:
    """Split one behavioural run into the activation-collection set and a holdout.

    §2.3.4 requires the activation-collection set (steering vectors, probes, the
    natural-variability statistics), the calibration set (patching corruption and
    noising means) and the per-experiment test sets to be **mutually disjoint**,
    partitioned once up front.  This does the first cut; the balanced calibration
    set of §5.2/§6.1 is then selected *within* the holdout, and the test trials
    from what is left, so all three stay disjoint.
    """
    import numpy as np

    order = np.random.default_rng(cfg.seed if seed is None else seed).permutation(len(trials))
    activation = np.sort(order[: cfg.activation_n])
    holdout = np.sort(order[cfg.activation_n:])
    return (
        ([trials[i] for i in activation], [rendered[i] for i in activation]),
        ([trials[i] for i in holdout], [rendered[i] for i in holdout]),
    )
