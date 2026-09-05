"""Configuration and shared filesystem paths for vonto.

Every path lives under ``$PROJECT_ROOT`` (default ``/scratch/qi/project`` — a
scratch filesystem with real space, not the quota-limited home directory) so
notebooks stay portable across machines via one env var, and large
downloads/generated data never land in the home filesystem by accident.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/scratch/qi/project"))

DATA_RAW = PROJECT_ROOT / "data" / "raw"
TRIVIAQA_DIR = DATA_RAW / "triviaqa"
TRIVIAQA_DISK = TRIVIAQA_DIR / "rc_nocontext_validation"

#: Procedurally generated dataset seeds (`vonto.dataset`) — distinct from
#: `DATA_RAW` (downloaded, unmodified source data).
DATA_PREPARED_DIR = PROJECT_ROOT / "data" / "prepared"

CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
HF_CACHE = CHECKPOINTS_DIR / ".hf_cache"

#: Grades cache (`vonto.grading`) — distinct from `DATA_PREPARED_DIR`/
#: `DATA_RAW`, since a grade is neither raw source data nor a generated seed.
GRADES_DIR = PROJECT_ROOT / "results" / "grades"

#: model_key -> HuggingFace checkpoint. Kept intentionally small — add entries
#: only as a real notebook actually needs a new model, not speculatively.
MODELS: dict[str, str] = {
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
}

#: §2.3.1 / §3.2 — grading and the hedging check.
GRADER_MODEL = "gpt-4o-mini"

#: The setup script's own credentials file (HF + OpenAI tokens) — same
#: location and ``KEY=VALUE``/``$REF`` format `archive/vconf/config.py` reads,
#: since it's the same underlying setup, not a vonto-specific file.
CREDENTIALS_FILE = Path(os.environ.get("THESIS_ENV_FILE", str(Path.home() / ".thesis-experiment.env")))


def load_credentials() -> None:
    """Read the ``KEY=VALUE`` credentials file the setup script wrote on
    home, exporting anything not already in ``os.environ`` (which wins), then
    point HuggingFace's own cache at ``$PROJECT_ROOT`` instead of its home-
    directory default — model/dataset downloads have no business landing on a
    quota-limited home filesystem. Uses ``setdefault`` throughout, so an
    already-configured environment (e.g. a shared cluster setup) is never
    overridden.
    """
    found: dict[str, str] = {}
    if CREDENTIALS_FILE.exists():
        for line in CREDENTIALS_FILE.read_text().splitlines():
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
    os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE / "hub"))
