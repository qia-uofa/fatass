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
    # Explicit encoding: these files use em-dashes and typographic
    # punctuation, and Path.read_text()'s platform-default encoding is
    # cp1252 on Windows, which can't decode arbitrary UTF-8 byte sequences.
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def load_topology_edit_system_prompt(name: str, extra: str | None = None) -> str | None:
    """`conventions.md` (the static node/transform/fatass.free() reference
    every free_topology() caller needs, now that it has no read access to
    the rest of the topology tree to learn those conventions by example)
    followed by the command-specific prompt named `name`, followed by
    `extra` if given — used by `create`/`modify`, the two CLI commands
    that go through free_topology(). `extra` is where a target node's own
    class contributes guidance specific to its kind (e.g.
    `NodeList.create_sys_prompt()`/`modify_sys_prompt()`), so a plain
    `Node` edit doesn't pay for guidance it doesn't need."""
    parts = [
        text
        for text in (load_system_prompt("conventions"), load_system_prompt(name), extra)
        if text
    ]
    return "\n\n".join(parts) or None
