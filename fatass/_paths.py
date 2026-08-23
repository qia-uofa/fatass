from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOPOLOGY_ROOT = REPO_ROOT / "fatass" / "topology"
NODES_ROOT = REPO_ROOT / "nodes"
ARCHIVE_ROOT = REPO_ROOT / "archive"
STATE_DIR = REPO_ROOT / ".fatass"
ENV_PATH = STATE_DIR / ".env"
LOG_PATH = REPO_ROOT / "log"
