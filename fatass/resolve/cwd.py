import re

from .._internal.paths import ENV_PATH as _ENV_PATH
from ..errors import TopologyValidationError
from . import dotenv

ROOT = "~"
"""Sentinel meaning "the true topology root, not any specific node" — the
value of FATASS_NODE when no prefix should be added, and the result of
`expand()` when a path expression walks back to that root."""

_ENV_KEY = "FATASS_NODE"

_SPLIT = re.compile(r"(\.+)")

_session_node: str | None = None
"""In-process override of the current node, set by `shell` while its REPL
loop is running. Each `fatass shell` invocation is its own OS process, so
this module-level variable naturally isolates concurrent shell sessions
from each other — unlike FATASS_NODE in .fatass/.env, which is shared by
every process (concurrent shells, and any other command run meanwhile).
None means "no shell session active", i.e. fall back to the dotenv file."""


def enter_session(node_path: str) -> None:
    """Start a `shell` session: from here until `exit_session()`,
    `read_current_node`/`write_current_node` use this in-memory value
    instead of the shared dotenv file, so `cd` inside this shell no
    longer affects other processes (including other concurrent shells)."""
    global _session_node
    _session_node = node_path


def exit_session() -> None:
    global _session_node
    _session_node = None


def read_current_node() -> str:
    """The node `sh`/`free`/`cd` target expressions are resolved relative
    to — the active shell session's in-memory node if one is running,
    else FATASS_NODE from the dotenv file, or ROOT if there's no file or
    no such variable in it."""
    if _session_node is not None:
        return _session_node
    return dotenv.read(_ENV_PATH).get(_ENV_KEY, ROOT)


def write_current_node(node_path: str) -> None:
    global _session_node
    if _session_node is not None:
        _session_node = node_path
        return
    dotenv.write_var(_ENV_PATH, _ENV_KEY, node_path)


def display_current_node(current: str | None = None) -> str:
    """"~.tests.list2" (or just "~" at the root) — the current node in
    the same absolute "~."-prefixed form used elsewhere (ls, resolve
    targets), for anything that shows it to a human: the `shell` prompt,
    and each dispatched command's line in ./log."""
    if current is None:
        current = read_current_node()
    return current if current == ROOT else f"~.{current}"


def expand(raw: str, current: str | None = None) -> str:
    """Resolve a node-path expression relative to the current node (the
    current FATASS_NODE, read fresh unless `current` is given explicitly).

    - A leading "~" resets the base to the true topology root, ignoring
      the current node entirely ("~.something" == "something", plain
      "~" == ROOT).
    - Otherwise the expression is resolved against the current node
      (itself just ROOT, i.e. no prefix, if that's what it is).
    - A run of N>=1 consecutive dots means: ascend (N-1) levels from
      wherever the walk currently stands, then (if a name follows)
      descend into it. So "." stays put, ".." goes up one level (to the
      current node's parent), "node1..node2" is "node1's parent's child
      node2" (node1 is pushed, then the ".." pops it back off before
      "node2" is pushed), and so on for more dots.

    Returns the resolved absolute node path, or ROOT if the walk lands
    back at the topology root (there's no node there). Raises
    TopologyValidationError if it tries to go above the root.
    """
    if current is None:
        current = read_current_node()

    parts = _SPLIT.split(raw)

    if parts[0] == ROOT:
        stack: list[str] = []
    elif current == ROOT:
        stack = []
    else:
        stack = current.split(".")

    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part and not (i == 0 and part == ROOT):
                stack.append(part)
        else:
            hops = len(part) - 1
            for _ in range(hops):
                if not stack:
                    raise TopologyValidationError(
                        f"{raw!r} goes above the topology root"
                    )
                stack.pop()

    return ".".join(stack) if stack else ROOT
