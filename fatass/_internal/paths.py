from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TOPOLOGY_ROOT = REPO_ROOT / "fatass" / "topology"
HOME_ROOT = REPO_ROOT / "home"
ARCHIVE_ROOT = REPO_ROOT / "archive"
STATE_DIR = REPO_ROOT / ".fatass"
ENV_PATH = STATE_DIR / ".env"
LOG_PATH = REPO_ROOT / "log"
SHELL_HISTORY_PATH = STATE_DIR / "shell_history"
"""Persisted `>>> ` line history for `fatass shell` (prompt_toolkit
FileHistory format) — shared across every `fatass shell` invocation, past
and present, so `fatass debug` can show what was actually typed at the
`>>> ` prompt, not the OS terminal's own (bash/PowerShell) history."""
SHELL_OUTPUT_PATH = STATE_DIR / "shell_output"
"""Persisted transcript of `fatass shell`'s own console output (plain
text, one `>>> <line>` header followed by whatever that command printed
to stdout/stderr) — shared across every `fatass shell` invocation, same
append-only convention as SHELL_HISTORY_PATH, so `fatass debug` can also
see what a command actually *printed* (errors, results), not just what
was typed."""
