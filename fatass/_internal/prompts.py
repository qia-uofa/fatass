from pathlib import Path

from .paths import REPO_ROOT

PROMPTS_ROOT = REPO_ROOT / "fatass" / "prompts"


def load_system_prompt(name: str) -> str | None:
    """The contents of `fatass/prompts/<name>.md`, or None if it doesn't
    exist — callers append this (via `--append-system-prompt`) rather than
    require it, so a missing file just means no extra guidance, not an
    error."""
    path = PROMPTS_ROOT / f"{name}.md"
    if not path.is_file():
        return None
    text = path.read_text().strip()
    return text or None
