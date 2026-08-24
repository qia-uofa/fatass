from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TOPOLOGY_ROOT = REPO_ROOT / "fatass" / "topology"
HOME_ROOT = REPO_ROOT / "home"
ARCHIVE_ROOT = REPO_ROOT / "archive"
STATE_DIR = REPO_ROOT / ".fatass"
ENV_PATH = STATE_DIR / ".env"
LOG_PATH = REPO_ROOT / "log"
