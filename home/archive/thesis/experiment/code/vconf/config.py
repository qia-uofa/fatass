"""Configuration for the *How do LLMs Compute Verbal Confidence?* reproduction.

Every constant here is taken from the reproduction guidebook (the manual):
model checkpoints and layer counts (§2.2), layer sweeps (§2.9), trial pools and
counts (§2.7), the underdetermined-detail defaults (§13) and the filesystem
layout provisioned by ``scripts/setup/_.sh``.

Nothing in this module downloads or creates anything: the setup script has
already created ``$PROJECT_ROOT`` and its subdirectories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

# --------------------------------------------------------------------------- #
# Filesystem layout (created by scripts/setup/_.sh)
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/scratch/qi/project"))

DATA_RAW = PROJECT_ROOT / "data" / "raw"
TRIVIAQA_DIR = DATA_RAW / "triviaqa"
TRIVIAQA_DISK = TRIVIAQA_DIR / "rc_nocontext_validation"
BIGMATH_DIR = DATA_RAW / "bigmath"
MMLU_DIR = DATA_RAW / "mmlu"
PARTITIONS_DIR = PROJECT_ROOT / "data" / "partitions"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
HF_CACHE = CHECKPOINTS_DIR / ".hf_cache"
ACTIVATIONS_DIR = PROJECT_ROOT / "activations"
RESULTS_DIR = PROJECT_ROOT / "results"
GRADES_DIR = RESULTS_DIR / "grades"
LOGS_DIR = RESULTS_DIR / "logs"
FIGURES_DIR = RESULTS_DIR / "figures"

CREDENTIALS_FILE = Path(
    os.environ.get("THESIS_ENV_FILE", str(Path.home() / ".thesis-experiment.env"))
)


def load_credentials(path: Path | None = None) -> dict[str, str]:
    """Read the ``KEY=VALUE`` credentials file the setup script wrote on home.

    Values already present in ``os.environ`` win; missing keys are exported so
    that ``huggingface_hub`` / ``openai`` pick them up.
    """
    path = path or CREDENTIALS_FILE
    found: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if value.startswith("$"):  # e.g. HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
                value = found.get(value[1:], os.environ.get(value[1:], ""))
            found[key] = value
    for key, value in found.items():
        if value and not os.environ.get(key):
            os.environ[key] = value
    os.environ.setdefault("PROJECT_ROOT", str(PROJECT_ROOT))
    os.environ.setdefault("HF_HOME", str(HF_CACHE))
    return found


# --------------------------------------------------------------------------- #
# Models under test (§2.2)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ModelSpec:
    """A checkpoint from §2.2 together with the properties the manual states."""

    key: str
    checkpoint: str
    n_layers: int
    role: str
    gated: bool = False


MODELS: dict[str, ModelSpec] = {
    "gemma": ModelSpec("gemma", "google/gemma-3-27b-it", 62, "primary", gated=True),
    "qwen": ModelSpec("qwen", "Qwen/Qwen2.5-7B-Instruct", 28, "architecture generalization"),
    "magistral": ModelSpec(
        "magistral", "mistralai/Magistral-Small-2506", 40, "reasoning-model generalization"
    ),
}

GRADER_MODEL = "gpt-4o-mini"  # §2.3.1 / §3.2 — grading and the hedging check

# --------------------------------------------------------------------------- #
# Layer sweeps (§2.9)
# --------------------------------------------------------------------------- #

GEMMA_LAYER_SWEEP: tuple[int, ...] = (
    0, 10, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 40, 50, 61,
)
QWEN_LAYER_SWEEP: tuple[int, ...] = tuple(range(28))
MAGISTRAL_LAYER_SWEEP: tuple[int, ...] = tuple(range(40))

LAYER_SWEEPS: dict[str, tuple[int, ...]] = {
    "gemma": GEMMA_LAYER_SWEEP,
    "qwen": QWEN_LAYER_SWEEP,
    "magistral": MAGISTRAL_LAYER_SWEEP,
}

# Attention blocking uses its own convention (§11.2): a window of 12 consecutive
# layers centred on each x-axis position.
ATTENTION_WINDOW = 12
ATTENTION_SWEEP: tuple[int, ...] = (
    10, 15, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 45, 50, 56,
)

# --------------------------------------------------------------------------- #
# Trial counts (§2.3.1, §2.7, §12.2)
# --------------------------------------------------------------------------- #

# Behavioural / calibration run sizes, per model + prompt (§2.3.1, §3.3).
BEHAVIORAL_N = {
    ("gemma", "categorical"): 7858,
    ("gemma", "numeric"): 8008,
    ("gemma", "minimal_numeric"): 2000,
    ("magistral", "categorical"): 5000,
}

ACTIVATION_SET_N = 3000  # §2.3.4 item 1
CALIBRATION_N = 100  # §2.3.4 item 2 — 50 high + 50 low
CALIBRATION_HIGH = 50
CALIBRATION_LOW = 50

STEERING_VECTOR_N = 25  # §4.2 — 25 highest + 25 lowest, correct answers only

# Per-experiment test-set sizes for Gemma (§2.7) and Qwen (§12.2).
TRIAL_COUNTS: dict[str, dict[str, int]] = {
    "gemma": {"steering": 200, "patching": 200, "noising": 400, "swap": 400, "attention": 500},
    "qwen": {"steering": 150, "patching": 200, "noising": 300, "swap": 200, "attention": 500},
    "magistral": {"patching": 200, "noising": 400, "swap": 400},
}

# Qwen noising split (§12.2): 200 high-confidence + 100 low-confidence.
QWEN_NOISING_SPLIT = (200, 100)

SWAP_LOW_POOL_AVAILABLE = 221  # §2.7 — low pool is sampled with replacement to 400

# --------------------------------------------------------------------------- #
# Underdetermined-detail defaults (§13)
# --------------------------------------------------------------------------- #

RIDGE_ALPHA = 1.0  # §13 #6
LOGREG_C = 1.0  # §13 #7
PROBE_FOLDS = 5  # §9.1
ECE_BINS = 10  # §13 #8
OOD_PAIRS = 100_000  # §13 #9
DONOR_QUANTILE_BINS = 10  # §13 #10
TRIVIAQA_SPLIT = "validation"  # §13 #1
TRIVIAQA_CONFIG = "rc.nocontext"
MMLU_SPLIT = "test"  # §13 #14

SEED = 0

# Generation lengths stated by the manual (§2.2).
MAX_NEW_TOKENS_NUMERIC = 4
MAX_NEW_TOKENS_MAGISTRAL = 1024
# Phase-0 answer generation length is not stated for the categorical prompt; 64
# tokens comfortably covers a TriviaQA answer plus the trailing
# ``**Confidence**: $CLASS`` line that the Phase-0 prompt also asks for.
MAX_NEW_TOKENS_PHASE0 = 64

# --------------------------------------------------------------------------- #
# Run configuration
# --------------------------------------------------------------------------- #


@dataclass
class RunConfig:
    """Everything an experiment needs to know about *which* run it is.

    The defaults are the manual's primary setting: Gemma 3 27B, categorical
    prompt, TriviaQA.  :func:`preset` builds the other settings the manual
    describes, and :meth:`scaled` produces a smaller but structurally identical
    run for smoke-testing the pipeline on limited compute.
    """

    model_key: str = "gemma"
    prompt_kind: str = "categorical"  # categorical | numeric | minimal_numeric | magistral
    dataset: str = "triviaqa"  # triviaqa | bigmath | mmlu
    layers: tuple[int, ...] = GEMMA_LAYER_SWEEP
    activation_n: int = ACTIVATION_SET_N
    calibration_n: int = CALIBRATION_N
    behavioral_n: int = 7858
    trial_counts: dict[str, int] = field(
        default_factory=lambda: dict(TRIAL_COUNTS["gemma"])
    )
    steering_alphas: tuple[float, ...] = (2.0, 5.0)
    steering_scale_fraction: float = 0.03  # §4.2 — 3% of the residual norm
    positions: tuple[str, ...] = ("PANL", "PANL+1", "CC", "FCC")
    attention_sweep: tuple[int, ...] = ATTENTION_SWEEP
    attention_window: int = ATTENTION_WINDOW
    use_chat_template: bool = True  # §13 #2
    dtype: str = "bfloat16"
    device: str = "cuda"  # every model/tensor computation runs on the GPU
    attn_implementation: str | None = None  # "eager" is required for Experiment 8
    max_new_tokens_phase0: int = MAX_NEW_TOKENS_PHASE0
    seed: int = SEED
    batch_size: int = 8
    name: str = "gemma-categorical-triviaqa"

    @property
    def model(self) -> ModelSpec:
        return MODELS[self.model_key]

    @property
    def checkpoint(self) -> str:
        return self.model.checkpoint

    @property
    def n_layers(self) -> int:
        return self.model.n_layers

    def scaled(self, **overrides) -> "RunConfig":
        """Return a copy with the given fields replaced (used for reduced runs)."""
        if "trial_counts" in overrides:
            counts = dict(self.trial_counts)
            counts.update(overrides.pop("trial_counts"))
            overrides["trial_counts"] = counts
        return replace(self, **overrides)


def preset(name: str) -> RunConfig:
    """Build one of the manual's named settings.

    ``gemma-categorical``  §2.5.1 main experiments
    ``gemma-numeric``      §12.1 axis 1
    ``gemma-minimal``      §2.5.3 / §11 attention blocking
    ``qwen-categorical``   §12.2 axis 2
    ``gemma-bigmath`` / ``gemma-mmlu``   §12.3 axis 3
    ``magistral``          §12.4 axis 4
    """
    if name == "gemma-categorical":
        return RunConfig()
    if name == "gemma-numeric":
        return RunConfig(
            prompt_kind="numeric",
            behavioral_n=BEHAVIORAL_N[("gemma", "numeric")],
            name="gemma-numeric-triviaqa",
        )
    if name == "gemma-minimal":
        return RunConfig(
            prompt_kind="minimal_numeric",
            behavioral_n=BEHAVIORAL_N[("gemma", "minimal_numeric")],
            attn_implementation="eager",
            # §11.3: this prompt exists to minimise the template tokens between
            # PANL and CC, so it is fed as raw text (§13 #2 leaves the choice
            # open) — a chat template would reinsert turn markers there and put
            # the PANL+1 control on a special token.
            use_chat_template=False,
            name="gemma-minimal-numeric-triviaqa",
        )
    if name == "qwen-categorical":
        return RunConfig(
            model_key="qwen",
            layers=QWEN_LAYER_SWEEP,
            trial_counts=dict(TRIAL_COUNTS["qwen"]),
            name="qwen-categorical-triviaqa",
        )
    if name == "gemma-bigmath":
        return RunConfig(dataset="bigmath", name="gemma-categorical-bigmath")
    if name == "gemma-mmlu":
        return RunConfig(dataset="mmlu", name="gemma-categorical-mmlu")
    if name == "magistral":
        return RunConfig(
            model_key="magistral",
            prompt_kind="magistral",
            layers=MAGISTRAL_LAYER_SWEEP,
            behavioral_n=BEHAVIORAL_N[("magistral", "categorical")],
            trial_counts=dict(TRIAL_COUNTS["magistral"]),
            attn_implementation="eager",
            name="magistral-categorical-triviaqa",
        )
    raise KeyError(f"unknown preset: {name!r}")
