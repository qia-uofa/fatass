import contextvars
import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

from ._paths import TOPOLOGY_ROOT
from .errors import FreeCoercionError, FreeError
from .node import Node

_current_node: contextvars.ContextVar[type[Node]] = contextvars.ContextVar(
    "fatass_current_node"
)

_RESULT_SENTINEL = ".fatass-result.json"

_ALLOWED_TOOLS = "Read,Write,Edit,Glob,Grep"

_PRIMITIVE_TYPES = (str, int, float, bool, list, dict)


def _invoke_claude(cwd: Path, add_dirs: list[Path], prompt: str) -> subprocess.CompletedProcess:
    """Run the `claude` CLI non-interactively, scoped to file-editing tools.
    Shared by `free()` (writable = the current transform's owning node) and
    `fatass.scaffold` (writable = wherever a node/transform is being
    scaffolded under fatass/topology/ — a different directory than any
    node's `nodes/` output, so it can't go through free() itself)."""
    command = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--allowedTools",
        _ALLOWED_TOOLS,
        "--permission-mode",
        "acceptEdits",
    ]
    for path in add_dirs:
        command += ["--add-dir", str(path)]

    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise FreeError("the `claude` CLI was not found on PATH") from exc


def free(readable: list[Node], prompt: str, returns: type | None = None) -> Any:
    """Invoke the Claude CLI agent.

    `writable` is not a parameter: a transform can only ever write into the
    `nodes/` directory of the node it belongs to, resolved implicitly from
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
    result = _invoke_claude(cwd=writable_dir, add_dirs=add_dirs, prompt=full_prompt)

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


def free_topology(cwd: Path, prompt: str) -> None:
    """Invoke the Claude CLI to write under fatass/topology/ itself — a
    node's node.py, a transform file, or anything else there.

    `free()` can't do this: it always writes into the *currently running
    transform's* owning node's `nodes/` directory, resolved from context,
    and topology/ isn't that. This has no such restriction — `cwd` says
    directly where to write, callable any time, not only from inside a
    transform. The whole topology tree is passed as readable context
    (not just `cwd`), since scaffolding one node's file often needs to see
    another's — e.g. importing a dependency's `Node` class by path.

    Used by `fatass.scaffold` (behind the `create`/`modify` CLI commands)
    to flesh out or edit a node/transform file with a prompt.
    """
    result = _invoke_claude(cwd=cwd, add_dirs=[TOPOLOGY_ROOT], prompt=prompt)
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
