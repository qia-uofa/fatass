from pathlib import Path

from ..errors import TopologyValidationError
from ..topology_ops import scaffold
from ..topology_ops.scaffold import _assets_dir, _node_dir
from .cwd import ROOT, expand

_ASSETS_ROOT_MARKERS = ("", ".", "./")


def resolve(target: str) -> Path:
    """Resolve a CLI target string — shared by `sh` and `free` — to a
    directory:

    - "node1.node2" -> the node's own directory under fatass/topology/
      (its own <name>.py, __init__.py, transform files, ...).
    - "transform@node1.node2" -> that node's own directory too, since a
      transform file now sits directly in it (no separate transforms/
      subdirectory) — the agent sees the whole node, not an isolated
      transform-only view.
    - "node1.node2/rel/path" -> a path under the node's home/ assets
      directory ("/./" or trailing "/" for the assets directory itself);
      a path naming a file resolves to that file's parent directory, so
      the file itself can be referenced bare wherever the resolved
      directory is used.

    Every node-path portion above is first expanded relative to the
    current node (see fatass.resolve.cwd.expand) — FATASS_NODE from the dotenv
    file is prefixed on, "." /".."/etc. navigate from it, and a leading
    "~" ignores it for an absolute path. A node-path portion that expands
    to ROOT ("~", the true topology root — no FATASS_NODE set, or an
    explicit "~") maps to the topology/home root directory itself for
    the plain and "/" forms; "transform@~..." is rejected, since the
    root isn't a node and has no transforms of its own.

    The node-path portion before the first "/" must be non-empty — a
    target that starts with "/" (e.g. an unquoted "~/rel/path" that a
    shell tilde-expanded into an absolute filesystem path before fatass
    ever saw it, stripping the leading "~" entirely) is rejected rather
    than silently resolving against the current node, which is what an
    empty node-path expression would otherwise do. Use "~/" (trailing
    slash, rel="") or "~/." for the topology/home root's assets
    directory itself.
    """
    if "/" in target:
        node_expr, rel = target.split("/", 1)
        if not node_expr:
            raise TopologyValidationError(
                f"empty node path before '/' in {target!r} — if this came "
                "from an unquoted '~/...', your shell tilde-expanded it "
                "before fatass saw it; quote it or use '~.' instead"
            )
        node_path = expand(node_expr)
        if node_path == ROOT:
            base = scaffold._HOME_ROOT
        else:
            if not _node_dir(node_path).is_dir():
                raise TopologyValidationError(f"no node at {node_path!r}")
            base = _assets_dir(node_path)
        path = base if rel in _ASSETS_ROOT_MARKERS else base / rel
        return path if path.is_dir() else path.parent

    if "@" in target:
        transform_name, node_expr = target.split("@", 1)
        node_path = expand(node_expr)
        if node_path == ROOT:
            raise TopologyValidationError(
                "'~' (the topology root) isn't a node and has no transforms"
            )
        node_dir = _node_dir(node_path)
        if not (node_dir / f"{transform_name}.py").is_file():
            raise TopologyValidationError(
                f"no transform named {transform_name!r} under {node_path!r}"
            )
        return node_dir

    node_path = expand(target)
    if node_path == ROOT:
        return scaffold._TOPOLOGY_ROOT
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")
    return node_dir


def resolve_file(target: str) -> Path:
    """Resolve a CLI target string — for `vim` — to an actual openable
    file, using the same "node1.node2" / "transform@node1.node2" /
    "node1.node2/rel/path" grammar as `resolve()` above. `resolve()` always
    returns a directory (a cwd for `sh`/`free`), collapsing a "/" file
    target to its parent; this instead keeps the file itself:

    - "node1.node2" -> the node's own <name>.py class file.
    - "transform@node1.node2" -> that transform's own .py file.
    - "node1.node2/rel/path" -> that path under the node's home/ assets
      directory (a trailing "/" or "/./" names the assets directory
      itself, opened as-is — vim browses a directory fine). Unlike the
      plain/"@" forms, the file need not already exist here: vim creates
      it on save, same as running `vim newfile.txt` at a shell.

    As in `resolve()`, the node-path portion before the first "/" must be
    non-empty (see there for why — an unquoted "~/..." can get shell
    tilde-expanded before fatass sees it).
    """
    if "/" in target:
        node_expr, rel = target.split("/", 1)
        if not node_expr:
            raise TopologyValidationError(
                f"empty node path before '/' in {target!r} — if this came "
                "from an unquoted '~/...', your shell tilde-expanded it "
                "before fatass saw it; quote it or use '~.' instead"
            )
        node_path = expand(node_expr)
        if node_path == ROOT:
            base = scaffold._HOME_ROOT
        else:
            if not _node_dir(node_path).is_dir():
                raise TopologyValidationError(f"no node at {node_path!r}")
            base = _assets_dir(node_path)
        return base if rel in _ASSETS_ROOT_MARKERS else base / rel

    if "@" in target:
        transform_name, node_expr = target.split("@", 1)
        node_path = expand(node_expr)
        if node_path == ROOT:
            raise TopologyValidationError(
                "'~' (the topology root) isn't a node and has no transforms"
            )
        node_dir = _node_dir(node_path)
        transform_file = node_dir / f"{transform_name}.py"
        if not transform_file.is_file():
            raise TopologyValidationError(
                f"no transform named {transform_name!r} under {node_path!r}"
            )
        return transform_file

    node_path = expand(target)
    if node_path == ROOT:
        raise TopologyValidationError(
            "'~' (the topology root) isn't a node and has no class file"
        )
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")
    file_stem = node_path.rsplit(".", 1)[-1]
    return node_dir / f"{file_stem}.py"
