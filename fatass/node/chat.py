import subprocess
from pathlib import Path

from ..errors import FreeError
from .node import Node

_CONFIG_DIR_NAME = ".claude_config"

_SYS_PROMPT = """## `Chat` — a node that manages a live `claude` CLI session's history and artifacts

This node's `home/` directory is where a real, interactive `claude` CLI
session (started via `fatass chat new <this.node.path>`, never a
`fatass.free()` call — no sandboxing, no `--allowedTools` restriction, a
genuine full-access conversation) is run from, and where its own session
history is kept: this node's own `.claude_config/` subdirectory is
passed to `claude` as its `CLAUDE_CONFIG_DIR`, a real `claude` CLI
environment variable, so every session ever started against this node
writes its own transcript there mechanically (not something an agent
decides) — never scattered across the machine's own default `~/.claude/`
tree. Anything else the session creates in `home/` while running (the
session's own cwd) is this node's own "artifacts", same as any other
node's `home/` content."""


class Chat(Node):
    """A `Node` that launches and tracks real, interactive `claude` CLI
    sessions — its `home/` directory is both the session's own working
    directory (so anything it creates there is a tracked artifact) and,
    via `CLAUDE_CONFIG_DIR`, where `claude`'s own session transcripts for
    every session ever run against this node accumulate (mechanically,
    a `claude` CLI environment variable — not something decided or
    written by fatass itself).

    `PROMPT` is this node's own seed message: `start()`'s default first
    message when none is given explicitly. Not a system prompt and not
    sandboxed — a genuine, ordinary `claude` conversation."""

    PROMPT: str = ""

    @classmethod
    def _config_dir(cls) -> Path:
        config_dir = cls._assets_dir() / _CONFIG_DIR_NAME
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @classmethod
    def start(cls, prompt: str | None = None) -> subprocess.CompletedProcess:
        """Launch a brand-new, real interactive `claude` CLI session —
        never a `fatass.free()` call, so no `--allowedTools`/permission-
        mode sandboxing at all, exactly like running `claude` by hand.
        Blocks until the session's window/conversation is closed, same
        as `free()`'s own interactive path.

        `cwd` is this node's own `home/` directory (so anything the
        session creates there is a tracked artifact of this chat); the
        `CLAUDE_CONFIG_DIR` environment variable is pointed at this
        node's own `.claude_config/` subdirectory, so `claude`'s own
        session transcript/history bookkeeping for THIS call lands there
        mechanically — a real CLI environment variable `claude` itself
        already honors, not any fatass-side logging. Every call
        accumulates into the same directory, so `home/.claude_config/`
        ends up holding this node's whole session history, not just its
        latest one.

        `prompt` (default: this node's own `PROMPT`) seeds the session's
        first message; empty means no seed message at all (`claude`
        opens to its own blank prompt)."""
        from ..core.free import _claude_binary, _detached_env, _run_in_new_window  # local: avoid a cycle

        cwd = cls._assets_dir()
        cwd.mkdir(parents=True, exist_ok=True)
        config_dir = cls._config_dir()

        env = _detached_env()
        env["CLAUDE_CONFIG_DIR"] = str(config_dir)

        seed_prompt = cls.PROMPT if prompt is None else prompt
        command = [_claude_binary(), "--name", cls.__name__]
        if seed_prompt:
            command.append(seed_prompt)

        try:
            return _run_in_new_window(command, cwd=cwd, env=env)
        except FileNotFoundError as exc:
            raise FreeError(
                f"the `claude` CLI was not found at {command[0]!r} ({exc}) — "
                f"set FATASS_CLAUDE_BIN in .fatass/.env to the full path to "
                f"the claude executable if PATH alone can't find it here"
            ) from exc

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return _SYS_PROMPT
