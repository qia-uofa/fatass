from pathlib import Path

from .._internal.fs import force_rmtree
from ..node.node import Node
from ..core.transform import _import_node, discover
from ..errors import TopologyValidationError
from .scaffold import _assets_dir, _node_dir


def _is_node(node_path: str) -> bool:
    node_dir = _node_dir(node_path)
    return (node_dir / f"{node_dir.name}.py").is_file()


def _direct_subnodes(node_path: str) -> list[str]:
    """Immediate nested nodes — node_path's own topology dir contains
    <name>/<name>.py — per inclusion (see blueprint/concepts/relations.md)."""
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        return []
    return [
        f"{node_path}.{child.name}"
        for child in node_dir.iterdir()
        if child.is_dir() and child.name != "__pycache__" and (child / f"{child.name}.py").is_file()
    ]


def _direct_dependencies(node_path: str) -> set[str]:
    """Nodes node_path's own transforms declare as Node-typed parameters —
    per dependency (see blueprint/concepts/relations.md)."""
    return {
        dep_cls._topology_path()
        for spec in discover(node_path)
        for dep_cls in spec.dependencies.values()
    }


def _closure(start: str, *, via_subnodes: bool, via_dependencies: bool) -> set[str]:
    """`start` plus every node reachable from it by repeatedly following
    subnode edges and/or dependency edges, per the two flags. Cycle-safe —
    dependency edges aren't required to be acyclic."""
    visited = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        neighbors = set()
        if via_subnodes:
            neighbors.update(_direct_subnodes(current))
        if via_dependencies:
            neighbors.update(_direct_dependencies(current))
        for neighbor in neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return visited


def _content_entries(node_path: str) -> list[Path]:
    """Entries directly under home/<node_path>/ that are this node's own
    content — anything that isn't a directory belonging to a nested
    subnode (those are a separate node's content, not this one's)."""
    assets_dir = _assets_dir(node_path)
    if not assets_dir.is_dir():
        return []
    return [
        entry
        for entry in assets_dir.iterdir()
        if not (entry.is_dir() and _is_node(f"{node_path}.{entry.name}"))
    ]


def _purge_one(node_path: str) -> int:
    """Delete node_path's own content — unless its class overrides
    `purge_self()` (e.g. Single/Array, which clear their fixed-name
    file(s) in place instead of deleting them), in which case that's used
    instead. Best-effort import: a node whose class fails to import (e.g.
    it's mid-edit) just falls back to the generic behavior below, same as
    before this override existed. Returns how many entries were purged."""
    try:
        node_cls = _import_node(node_path)
    except Exception:
        node_cls = None

    if node_cls is not None and node_cls.purge_self is not Node.purge_self:
        result = node_cls.purge_self()
        if result is not None:
            return result

    removed = 0
    for entry in _content_entries(node_path):
        if entry.is_dir():
            force_rmtree(entry)
        else:
            entry.unlink()
        removed += 1
    return removed


def purge_node(
    node_path: str, *, rs: bool = False, rd: bool = False, rsd: bool = False
) -> dict[str, int]:
    """Delete a node's own content from home/ — any file or directory
    under home/<node_path>/ that isn't itself a nested subnode's
    directory. Doesn't touch fatass/topology/.

    Which other nodes get the same treatment depends on the flags:

    - Neither: only `node_path` itself.
    - `rs`: also every node nested under it, recursively (subnode/
      inclusion edges only).
    - `rd`: also every node it depends on, recursively — a dependency's
      dependency, and so on (dependency edges only; cycle-safe).
    - `rs` and `rd` both set, `rsd` not set: two separate full passes —
      first the entire `rs` closure is purged, then, starting fresh from
      `node_path` again, the entire `rd` closure is purged. Each pass
      follows only its own edge type from `node_path` — a subnode's
      dependencies, or a dependency's subnodes, are never reached by
      either pass.
    - `rsd`: one combined traversal following *both* edge types together
      from the start, reaching things neither `rs` nor `rd` alone (nor
      their sequential combination above) would — a subnode's dependency,
      a dependency's subnode, and so on, transitively.

    Returns {node_path: entries_removed} for every node purged.
    """
    if not _node_dir(node_path).is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    if rsd:
        targets = _closure(node_path, via_subnodes=True, via_dependencies=True)
        return {target: _purge_one(target) for target in sorted(targets)}

    if rs and rd:
        result = {}
        for target in sorted(_closure(node_path, via_subnodes=True, via_dependencies=False)):
            result[target] = _purge_one(target)
        for target in sorted(_closure(node_path, via_subnodes=False, via_dependencies=True)):
            result[target] = result.get(target, 0) + _purge_one(target)
        return result

    targets = _closure(node_path, via_subnodes=rs, via_dependencies=rd)
    return {target: _purge_one(target) for target in sorted(targets)}
