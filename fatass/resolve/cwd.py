import re

from .._internal.naming import pascal_node_path, snake_case
from .._internal.paths import ENV_PATH as _ENV_PATH
from ..errors import TopologyValidationError
from . import dotenv

ROOT = "@"
"""Sentinel meaning "the true topology root, not any specific node" — the
value of FATASS_NODE when no prefix should be added, and the result of
`expand()` when a path expression walks back to that root. Glues
directly onto the path that follows with no separating dot ("@A.B.C",
not "@.A.B.C") when used as a prefix; alone (nothing following, real or
absolute) it's shown parenthesized ("(@)") — see `expand()` and
`display_current_node()`."""

PAREN_ROOT = f"({ROOT})"
"""The parenthesized spelling of `ROOT` — the form `ls` itself renders
for the synthetic root node (`(@)<Topology>(...)`), and (unlike the bare
`ROOT` character, which glues straight onto a following name with no
dot) the one that needs an explicit "." before further path segments:
"(@).A.B.C". Also valid entirely on its own, e.g. `ls (@)`."""

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
    """"@Tests.List2" (or "(@)" at the root) — the current node in the
    same absolute, PascalCase form used elsewhere (ls, resolve targets),
    for anything that shows it to a human: the `shell` prompt, each
    dispatched command's line in out/log, and the GUI's own pwd display."""
    if current is None:
        current = read_current_node()
    return PAREN_ROOT if current == ROOT else f"{ROOT}{pascal_node_path(current)}"


def expand(raw: str, current: str | None = None) -> str:
    """Resolve a node-path expression relative to the current node (the
    current FATASS_NODE, read fresh unless `current` is given explicitly).

    - A leading "@" (glued directly onto what follows, no dot — "@Foo",
      not "@.Foo") or the equivalent parenthesized "(@)" (which, unlike
      bare "@", DOES need a "." before further segments: "(@).Foo" — the
      form `ls` itself renders for the synthetic root label, and the one
      that reads naturally standing alone, e.g. "(@)" itself) resets the
      base to the true topology root, ignoring the current node entirely
      ("@Foo" == "Foo" when already at the root, plain "@"/"(@)" ==
      ROOT).
    - Otherwise the expression is resolved against the current node
      (itself just ROOT, i.e. no prefix, if that's what it is).
    - A run of N>=1 consecutive dots means: ascend (N-1) levels from
      wherever the walk currently stands, then (if a name follows)
      descend into it. So "." stays put, ".." goes up one level (to the
      current node's parent), "node1..node2" is "node1's parent's child
      node2" (node1 is pushed, then the ".." pops it back off before
      "node2" is pushed), and so on for more dots.
    - A segment starting with "[" (a Chain index, e.g. "[0]" or "[*]")
      attaches to whatever the walk just landed on instead of becoming
      its own dotted segment — "..[0]" indexes the current node's parent,
      ".[0]" indexes the current node itself. Without this, "." + "[0]"
      would naively join as "<current>.[0]" (a literal dot before the
      bracket, which no node path ever has — see `_split_index` in
      core/transform.py, which expects the index glued directly onto the
      preceding path segment, e.g. "members[0]", not "members.[0]").
      Ordinary indexing already glued onto a name in the same run (e.g.
      "members[0]" typed out in full) was never affected by this — only
      a bracket reached via dot-navigation shorthand needed this fix.
    - Every real name segment (a bare one, or the name part of
      "name[idx]") must be PascalCase — matching that node's own class
      name, not its snake_case directory name — and is converted back
      via `snake_case()` (see `Node` naming conventions/`fatass touch`)
      before being pushed onto the walk. This is the single choke point
      almost every command's own node.path argument passes through
      (directly, or via `commands._targets.resolve_node_path` and
      friends, which just call this), so enforcing/converting it here
      makes it universal without needing every call site of its own to
      remember to.

    Returns the resolved absolute node path, or ROOT if the walk lands
    back at the topology root (there's no node there). Raises
    TopologyValidationError if it tries to go above the root, if a
    leading "[" segment has no node to attach to (the walk is at the
    root), or if a real name segment isn't PascalCase."""
    if current is None:
        current = read_current_node()

    paren_prefix = PAREN_ROOT + "."
    if raw == PAREN_ROOT:
        stack: list[str] = []
        remainder = ""
    elif raw.startswith(paren_prefix):
        stack = []
        remainder = raw[len(paren_prefix):]
    elif raw.startswith(ROOT):
        stack = []
        remainder = raw[len(ROOT):]
    elif current == ROOT:
        stack = []
        remainder = raw
    else:
        stack = current.split(".")
        remainder = raw

    parts = _SPLIT.split(remainder)

    for i, part in enumerate(parts):
        if i % 2 == 0:
            if not part:
                continue
            if part.startswith("["):
                if not stack:
                    raise TopologyValidationError(
                        f"{raw!r}: {part!r} has no node to index — the "
                        f"walk is at the topology root"
                    )
                stack[-1] += part
            else:
                name, bracket, index = part.partition("[")
                if not name[0].isupper():
                    raise TopologyValidationError(
                        f"{raw!r}: node-path segment {name!r} must be "
                        f"PascalCase (start with an uppercase letter)"
                    )
                stack.append(snake_case(name) + bracket + index)
        else:
            hops = len(part) - 1
            for _ in range(hops):
                if not stack:
                    raise TopologyValidationError(
                        f"{raw!r} goes above the topology root"
                    )
                stack.pop()

    return ".".join(stack) if stack else ROOT
