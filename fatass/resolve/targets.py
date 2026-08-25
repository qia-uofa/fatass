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
    - "node1.node2:rel/path" -> a path under the node's home/ assets
      directory ("./" or "" for the assets directory itself); a path
      naming a file resolves to that file's parent directory, so the
      file itself can be referenced bare wherever the resolved directory
      is used.

    Every node-path portion above is first expanded relative to the
    current node (see fatass.resolve.cwd.expand) — FATASS_NODE from the dotenv
    file is prefixed on, "." /".."/etc. navigate from it, and a leading
    "~" ignores it for an absolute path. A node-path portion that expands
    to ROOT ("~", the true topology root — no FATASS_NODE set, or an
    explicit "~") maps to the topology/home root directory itself for
    the plain and ":" forms; "transform@~..." is rejected, since the
    root isn't a node and has no transforms of its own.
    """
    if ":" in target:
        node_expr, rel = target.split(":", 1)
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
