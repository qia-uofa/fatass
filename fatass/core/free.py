import contextvars
import dataclasses
import json
import platform
import subprocess
from pathlib import Path
from typing import Any

from .._internal.logs import get_logger
from .._internal.paths import TOPOLOGY_ROOT
from .._internal.prompts import load_system_prompt
from ..errors import FreeCoercionError, FreeError
from .node import Node

_current_node: contextvars.ContextVar[type[Node]] = contextvars.ContextVar(
    "fatass_current_node"
)

_RESULT_SENTINEL = ".fatass-result.json"

DEFAULT_ALLOWED_TOOLS = "Read,Write,Edit,Glob,Grep,Bash,WebSearch,WebFetch"
"""The full tool grant — unchanged default for any caller that doesn't
pass tools= explicitly. A caller whose prompt doesn't need all of these
(e.g. no network access, no shell) should narrow it, least-privilege."""

_PRIMITIVE_TYPES = (str, int, float, bool, list, dict)

DEFAULT_PERMISSION_MODE = "acceptEdits"
"""Safer than "bypassPermissions": file edits (Read/Write/Edit) are
auto-accepted so a headless run doesn't stall waiting for approval, but
Claude Code's own finer-grained safety checks (e.g. on risky Bash
commands) still apply instead of being skipped outright. A caller whose
prompt genuinely needs unattended shell access can still pass
permission_mode="bypassPermissions" explicitly."""


def _log_token_usage(logger, stdout: str) -> None:
    """`-p --output-format json` includes a top-level `usage` object with
    token counts (and a `total_cost_usd`). Best-effort: never fail the
    call over this parse, since the exact JSON shape is Claude Code's, not
    a contract fatass controls."""
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(parsed, dict):
        return
    usage = parsed.get("usage")
    if usage:
        logger.info(
            "free(): tokens=%s total_cost_usd=%s", usage, parsed.get("total_cost_usd")
        )


def _terminal_launch_command(command: list[str]) -> list[str]:
    """Wrap `command` so it opens in its own, visible terminal window while
    the wrapping call still blocks until that window's process exits —
    needed so callers (e.g. free() reading back .fatass-result.json right
    after) can keep treating this synchronously, same as the headless path.

    Windows: `start "<title>" /wait <command>` opens a new console window
    and has cmd.exe wait for it, which is what makes the block work. There
    is no equally universal mechanism on macOS/Linux (Terminal.app/
    osascript can't block the same way, and Linux has no single standard
    terminal emulator), so elsewhere this just runs `command` inline in
    whatever terminal this process already has — still a live, watchable
    conversation, just not spawned into a separate window."""
    if platform.system() == "Windows":
        return ["cmd", "/c", "start", "Claude", "/wait"] + command
    return command


def _invoke_claude(
    cwd: Path,
    add_dirs: list[Path],
    prompt: str,
    *,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    system_prompt: str | None = None,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> subprocess.CompletedProcess:
    """Run the `claude` CLI, scoped to file-editing tools. Shared by
    `free()` (writable = the current transform's owning node),
    `fatass.topology_ops.scaffold` (writable = wherever a node/transform is
    being scaffolded under fatass/topology/ — a different directory than
    any node's `home/` output, so it can't go through free() itself), and
    `fatass.core.adhoc` (writable = wherever `fatass free` was pointed at).

    `silent=False` (the default) opens a real, human-visible conversation —
    the agent's normal interactive session, seeded with `prompt` as the
    first message — and blocks until it's closed, so a human can watch or
    steer it. `silent=True` instead runs headlessly (`-p --output-format
    json`, output captured, no terminal, exits on its own when done) — pass
    it explicitly for unattended runs (e.g. a `populate.sh`-style batch
    script, or any `returns=...` call whose caller needs to keep going
    without a human closing a window first)."""
    logger = get_logger()
    add_dirs_str = ", ".join(str(path) for path in add_dirs)

    base_command = [
        "claude",
        "--allowedTools",
        tools,
        "--permission-mode",
        permission_mode,
    ]
    for path in add_dirs:
        base_command += ["--add-dir", str(path)]
    if system_prompt:
        base_command += ["--append-system-prompt", system_prompt]
    if model:
        base_command += ["--model", model]

    if silent:
        command = base_command + ["-p", prompt, "--output-format", "json"]
        logger.info(
            "free(): cwd=%s add_dirs=[%s] silent=True permission_mode=%s model=%s "
            "tools=%s prompt=%r",
            cwd,
            add_dirs_str,
            permission_mode,
            model,
            tools,
            prompt,
        )
        try:
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise FreeError("the `claude` CLI was not found on PATH") from exc

        logger.info("free(): exit=%s", result.returncode)
        logger.info("free(): stdout=%r", result.stdout)
        logger.info("free(): stderr=%r", result.stderr)
        _log_token_usage(logger, result.stdout)
        return result

    command = base_command + [prompt]
    logger.info(
        "free(): cwd=%s add_dirs=[%s] silent=False permission_mode=%s model=%s tools=%s "
        "prompt=%r (interactive session)",
        cwd,
        add_dirs_str,
        permission_mode,
        model,
        tools,
        prompt,
    )
    launch = _terminal_launch_command(command)
    try:
        result = subprocess.run(launch, cwd=cwd)
    except FileNotFoundError as exc:
        raise FreeError("the `claude` CLI was not found on PATH") from exc

    logger.info("free(): exit=%s (interactive session closed)", result.returncode)
    logger.info("free(): token usage unavailable — interactive sessions aren't captured")
    return result


def free(
    readable: list[Node],
    prompt: str,
    returns: type | None = None,
    *,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> Any:
    """Invoke the Claude CLI agent.

    `writable` is not a parameter: a transform can only ever write into the
    `home/` directory of the node it belongs to, resolved implicitly from
    the transform currently running (see fatass/transform.py).
    """
    try:
        owning_node = _current_node.get()
    except LookupError as exc:
        raise FreeError(
            "free() was called outside of a running transform "
            "(no owning node in context)"
        ) from exc

    writable_dir = owning_node._assets_dir()
    writable_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = prompt
    if returns is not None:
        full_prompt += (
            f"\n\nWhen finished, write your final result as JSON matching "
            f"the requested shape to a file named {_RESULT_SENTINEL} in "
            f"the current directory."
        )

    add_dirs = [node._assets_dir() for node in readable]
    result = _invoke_claude(
        cwd=writable_dir,
        add_dirs=add_dirs,
        prompt=full_prompt,
        permission_mode=permission_mode,
        silent=silent,
        system_prompt=load_system_prompt("transform"),
        model=model,
        tools=tools,
    )

    if result.returncode != 0:
        raise FreeError(
            f"claude CLI exited with {result.returncode}: {result.stderr}"
        )

    if returns is None:
        return None

    sentinel_path = writable_dir / _RESULT_SENTINEL
    if not sentinel_path.exists():
        raise FreeCoercionError(
            f"expected {_RESULT_SENTINEL} in {writable_dir}, agent didn't "
            f"write one"
        )
    try:
        raw = json.loads(sentinel_path.read_text())
    except json.JSONDecodeError as exc:
        raise FreeCoercionError(f"{_RESULT_SENTINEL} is not valid JSON") from exc
    finally:
        sentinel_path.unlink(missing_ok=True)

    return _coerce(raw, returns)


def free_topology(
    cwd: Path,
    prompt: str,
    *,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    system_prompt: str | None = None,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> None:
    """Invoke the Claude CLI to write under fatass/topology/ itself — a
    node's node.py, a transform file, or anything else there.

    `free()` can't do this: it always writes into the *currently running
    transform's* owning node's `home/` directory, resolved from context,
    and topology/ isn't that. This has no such restriction — `cwd` says
    directly where to write, callable any time, not only from inside a
    transform. The whole topology tree is passed as readable context
    (not just `cwd`), since scaffolding one node's file often needs to see
    another's — e.g. importing a dependency's `Node` class by path.

    Used by `fatass.topology_ops.scaffold` (behind the `create`/`modify` CLI commands)
    to flesh out or edit a node/transform file with a prompt.
    """
    result = _invoke_claude(
        cwd=cwd,
        add_dirs=[TOPOLOGY_ROOT],
        prompt=prompt,
        permission_mode=permission_mode,
        silent=silent,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
    )
    if result.returncode != 0:
        raise FreeError(f"claude CLI exited with {result.returncode}: {result.stderr}")


def _coerce(value: Any, returns: type) -> Any:
    if returns in _PRIMITIVE_TYPES:
        if not isinstance(value, returns):
            raise FreeCoercionError(
                f"expected {returns.__name__}, got {type(value).__name__}"
            )
        return value
    if dataclasses.is_dataclass(returns):
        if not isinstance(value, dict):
            raise FreeCoercionError(
                f"expected an object for {returns.__name__}, got "
                f"{type(value).__name__}"
            )
        try:
            return returns(**value)
        except TypeError as exc:
            raise FreeCoercionError(
                f"couldn't build {returns.__name__} from result: {exc}"
            ) from exc
    raise FreeCoercionError(f"unsupported returns type: {returns!r}")
