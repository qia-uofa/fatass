#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

# -----------------------------------------------------------------------------
# Environment provisioning for the "How do LLMs Compute Verbal Confidence?"
# reproduction (setup manual: Requirements / Filesystem layout / Environment
# setup / Data setup). Safe to re-run on a fresh machine or after a
# /scratch reset: every step checks for existing state before acting.
#
# Filesystem split (machine_info/filesystem):
#   - Home (~, NFS, shared low-quota, durable): code/topology/small artifacts.
#   - /scratch/qi (local ext4, private, large, NOT persistent): datasets,
#     model weights, conda/pip environments, activations, results.
# -----------------------------------------------------------------------------

# --- Paths (filesystem: authoritative locations on this machine) -----------
HOME_DIR="/home/stud_homes/s7846062"
SCRATCH_DIR="/scratch/qi"
PROJECT_ROOT="$SCRATCH_DIR/project"          # large/working data, per filesystem's guidance
CONDA_ENV_DIR="$SCRATCH_DIR/env"             # filesystem: already in use for a conda environment
ENV_FILE="$HOME_DIR/.thesis-experiment.env"  # credentials must survive a /scratch wipe -> kept on home NFS

# --- Requirements: confirm Python 3.10+ is available (setup_man Environment setup #1) ---
echo "Checking system python3 version..."
python3 --version

# --- Filesystem layout: create $PROJECT_ROOT subdirectories (setup_man Filesystem layout / Environment setup #2) ---
mkdir -p \
  "$PROJECT_ROOT/code" \
  "$PROJECT_ROOT/data/raw/triviaqa" \
  "$PROJECT_ROOT/data/raw/bigmath" \
  "$PROJECT_ROOT/data/raw/mmlu" \
  "$PROJECT_ROOT/data/partitions" \
  "$PROJECT_ROOT/checkpoints" \
  "$PROJECT_ROOT/checkpoints/.hf_cache" \
  "$PROJECT_ROOT/activations" \
  "$PROJECT_ROOT/results/grades" \
  "$PROJECT_ROOT/results/logs" \
  "$PROJECT_ROOT/results/figures"

# --- Credentials file: create a template on durable home storage if absent ---
# (setup_man Filesystem layout: HF_TOKEN/HUGGING_FACE_HUB_TOKEN/OPENAI_API_KEY,
# kept out of $PROJECT_ROOT since /scratch is not persistent across resets.)
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'EOF'
# Hugging Face token with the Gemma 3 license accepted for google/gemma-3-27b-it
HF_TOKEN=
HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
# OpenAI API key for gpt-4o-mini grading and hedging checks
OPENAI_API_KEY=
EOF
  chmod 600 "$ENV_FILE"
  echo "Created credentials template at $ENV_FILE - fill in HF_TOKEN and OPENAI_API_KEY."
fi

# --- Environment variables (setup_man Filesystem layout / Environment setup #6) ---
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
export PROJECT_ROOT
export HF_HOME="$PROJECT_ROOT/checkpoints/.hf_cache"
export HF_DATASETS_CACHE="$PROJECT_ROOT/data/raw/.hf_datasets_cache"
mkdir -p "$HF_DATASETS_CACHE"
set +a

# Mirror a .env file at $PROJECT_ROOT for tools that expect it there per the
# setup_man layout, without duplicating the durable secrets store.
cat > "$PROJECT_ROOT/.env" <<EOF
PROJECT_ROOT=$PROJECT_ROOT
HF_HOME=$HF_HOME
HF_TOKEN=$HF_TOKEN
HUGGING_FACE_HUB_TOKEN=$HUGGING_FACE_HUB_TOKEN
OPENAI_API_KEY=$OPENAI_API_KEY
HF_DATASETS_CACHE=$HF_DATASETS_CACHE
EOF
chmod 600 "$PROJECT_ROOT/.env"

# --- Python environment: reuse the conda env at $CONDA_ENV_DIR (filesystem: ---
# --- already in use for a conda environment there, conda-meta/etc layout) ---
if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found on PATH; install/initialize conda before continuing." >&2
  exit 1
fi

if [ ! -x "$CONDA_ENV_DIR/bin/python3" ]; then
  if [ -d "$CONDA_ENV_DIR/conda-meta" ]; then
    echo "Conda prefix exists at $CONDA_ENV_DIR but has no python installed; installing it now..."
    conda install -y -p "$CONDA_ENV_DIR" "python>=3.10"
  else
    echo "Creating conda environment at $CONDA_ENV_DIR (setup_man Software requirements: python >= 3.10)..."
    conda create -y -p "$CONDA_ENV_DIR" "python>=3.10"
  fi
else
  echo "Conda environment already present at $CONDA_ENV_DIR, reusing it."
fi

# --- Install required packages (setup_man Software / Environment setup #4) ---
conda run -p "$CONDA_ENV_DIR" pip install --upgrade pip
conda run -p "$CONDA_ENV_DIR" pip install \
  "torch>=2.3" "transformers>=4.50" accelerate datasets "scikit-learn>=1.3" \
  numpy scipy pandas matplotlib openai tqdm

# --- Verify GPU visibility and bf16 support (setup_man Environment setup #5) ---
conda run -p "$CONDA_ENV_DIR" python3 -c "
import torch
if torch.cuda.is_available():
    print('CUDA available:', torch.cuda.is_available())
    print('Device 0:', torch.cuda.get_device_name(0))
    print('bf16 supported:', torch.cuda.is_bf16_supported())
else:
    print('CUDA not available on this machine.')
"

# --- Hugging Face authentication (setup_man Environment setup #7) ---
# Requires the Gemma 3 license accepted on the google/gemma-3-27b-it model
# page; that acceptance itself is a manual, one-time web action and cannot
# be scripted here.
if [ -n "${HF_TOKEN:-}" ]; then
  conda run -p "$CONDA_ENV_DIR" huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential || true
else
  echo "HF_TOKEN is empty in $ENV_FILE - set it, then re-run this script to authenticate with huggingface-cli."
fi

# --- Data setup: TriviaQA (setup_man Data setup) ---
# rc.nocontext / unfiltered configuration, validation split, deduplicated on
# normalized question text before sampling; stored under data/raw/triviaqa.
# Big-Math and MMLU are named as "available on the Hugging Face hub" without
# a specific dataset repo id or configuration, so their download commands are
# left unspecified here rather than guessed.
TRIVIAQA_MARKER="$PROJECT_ROOT/data/raw/triviaqa/.downloaded"
if [ ! -f "$TRIVIAQA_MARKER" ]; then
  conda run -p "$CONDA_ENV_DIR" python3 -c "
import os
from datasets import load_dataset

ds = load_dataset('mandarjoshi/trivia_qa', 'rc.nocontext', split='validation')
seen = set()
deduped = 0
for row in ds:
    q = ' '.join(row['question'].strip().lower().split())
    if q not in seen:
        seen.add(q)
        deduped += 1
ds.save_to_disk(os.path.join(os.environ['PROJECT_ROOT'], 'data', 'raw', 'triviaqa', 'rc_nocontext_validation'))
print('TriviaQA validation rows:', len(ds), '| deduplicated unique questions:', deduped)
"
  touch "$TRIVIAQA_MARKER"
else
  echo "TriviaQA already downloaded at $PROJECT_ROOT/data/raw/triviaqa, skipping."
fi

echo "Environment setup complete."
