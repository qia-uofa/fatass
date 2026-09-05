import dataclasses
from pathlib import Path

import importlib
import pkgutil

from . import node as _node_pkg
from .node.node import Node
from .core.transform import _import_node, discover
from .errors import TopologyValidationError
from .topology_ops.scaffold import _all_node_paths, _node_dir


def _load_all_node_modules() -> None:
    """Import every fatass/node/*.py module — so each framework node
    kind it defines (Chain, Single, Array, Tuple, Repo, and any future
    one) is registered on `Node.__subclasses__()` before
    `_direct_node_subclasses()` reads it, without this file having to
    name them one by one."""
    for module_info in pkgutil.iter_modules(_node_pkg.__path__, prefix=f"{_node_pkg.__name__}."):
        importlib.import_module(module_info.name)


_load_all_node_modules()


def _direct_node_subclasses() -> tuple[type[Node], ...]:
    """Every fatass-framework base kind a node can be built on — Node's
    own *direct* subclasses that are themselves defined under the
    `fatass.node` package (Chain, Single, Array, Tuple, Repo, ...), as
    opposed to either a typed variant like SingleCsv (a subclass of
    Single, not of Node itself) or an ordinary topology-defined node
    (e.g. `class Cv(fatass.Node)`, which subclasses Node directly too,
    but lives under `fatass.topology.*` — exactly the "no special kind"
    case this is meant to fall back to "Node" for). Discovered from the
    live class hierarchy plus module path rather than a hardcoded list,
    so a new `fatass/node/<name>.py` direct subclass of Node is picked up
    here automatically."""
    prefix = f"{_node_pkg.__name__}."
    return tuple(
        sub for sub in Node.__subclasses__() if sub.__module__.startswith(prefix)
    )


def _base_class_name(node_cls: type[Node]) -> str:
    """The fatass base class a node is built on ("Chain"/"Single"/
    "Array"/"Tuple"/"Node"), not its own specific subclass name (which is
    just the PascalCase of its own path segment and so adds no
    information the path doesn't already carry) — nor a typed variant
    like "SingleCsv" (collapsed to "Single"). This is what `fatass ls`
    shows: it tells you the node's *kind* at a glance. Walks `node_cls`'s
    MRO (most specific first) for the first ancestor that's one of
    `_direct_node_subclasses()` — e.g. for a class built on SingleCsv,
    that's Single itself, not SingleCsv."""
    direct = _direct_node_subclasses()
    for base in node_cls.__mro__:
        if base in direct:
            return base.__name__
    return "Node"


@dataclasses.dataclass
class DependencySummary:
    path: str
    """Absolute topology path (no `~.` prefix — that's a display concern)."""
    class_name: str
    children: list[str]
    """Direct subnode names (bare, not full paths) of this dependency."""


@dataclasses.dataclass
class TransformInfo:
    name: str
    dependencies: list[DependencySummary]
    """One entry per Node-typed parameter, in declaration order — empty
    for a transform with no such dependency."""


@dataclasses.dataclass
class NodeSummary:
    path: str
    class_name: str
    children: list[str]
    """Direct subnode names (bare, not full paths)."""
    transforms: list[TransformInfo]


@dataclasses.dataclass
class NodeTree:
    path: str
    """Absolute topology path — "" for the synthetic root (see
    list_root_tree()), which has no path of its own."""
    class_name: str
    children: list["NodeTree"]
    """Every subnode, recursively — unlike NodeSummary.children (direct,
    bare names only), this goes all the way down. No transforms: `-r`
    is about the inclusion tree's shape, not how each node is built."""


def list_root() -> list[str]:
    """Top-level node names directly under fatass/topology/ — the listing
    for the true topology root (FATASS_NODE unset / expanded to "~"),
    which has no node file of its own and thus no class or transforms."""
    return sorted(path for path in _all_node_paths() if "." not in path)


def _direct_subnodes(node_path: str) -> list[str]:
    """Direct child names (e.g. "b" for "a.b" under "a") — the next path
    segment only, not full paths; nested descendants aren't included."""
    prefix = node_path + "."
    return sorted(
        path[len(prefix) :]
        for path in _all_node_paths()
        if path.startswith(prefix) and "." not in path[len(prefix) :]
    )


def list_node(node_path: str) -> NodeSummary:
    """The structured `fatass ls <node.path>` view: node_path's own class
    and direct subnodes, plus its transforms — each transform's
    dependencies carrying their own class + direct subnodes too, so a
    dependency's shape is visible without a separate `ls` call. Transforms
    are sorted with any transform literally named "build" first (the
    conventional entry point), otherwise keeping `discover()`'s
    alphabetical-by-filename order."""
    if not _node_dir(node_path).is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    node_cls = _import_node(node_path)
    specs = sorted(discover(node_path), key=lambda spec: spec.name != "build")

    transforms = [
        TransformInfo(
            name=spec.name,
            dependencies=[
                DependencySummary(
                    path=dep_cls._topology_path(),
                    class_name=_base_class_name(dep_cls),
                    children=_direct_subnodes(dep_cls._topology_path()),
                )
                for dep_cls in spec.dependencies.values()
            ],
        )
        for spec in specs
    ]

    return NodeSummary(
        path=node_path,
        class_name=_base_class_name(node_cls),
        children=_direct_subnodes(node_path),
        transforms=transforms,
    )


def list_node_tree(node_path: str) -> NodeTree:
    """The recursive `fatass ls -r <node.path>` view: node_path's own
    class, and every subnode nested beneath it, all the way down —
    unlike list_node()'s children (direct, bare names only). No
    transforms (see NodeTree)."""
    if not _node_dir(node_path).is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    node_cls = _import_node(node_path)
    children = [list_node_tree(f"{node_path}.{name}") for name in _direct_subnodes(node_path)]
    return NodeTree(path=node_path, class_name=_base_class_name(node_cls), children=children)


def list_root_tree() -> NodeTree:
    """The recursive `fatass ls -r ~` view — the whole topology, rooted
    at the synthetic "topology" class (matching `graph`'s root label)."""
    children = [list_node_tree(name) for name in list_root()]
    return NodeTree(path="", class_name="topology", children=children)


def list_dir(path: Path) -> list[str]:
    """Directory entry names, sorted — the raw `ls` view used for a '('
    (home/ asset directory) target. Unlike `list_node`'s subnodes (which
    aren't literally directories in the topology sense), these entries
    are real filesystem content, so a subdirectory gets a trailing "/"
    (classic `ls -F` convention) to distinguish it from a plain file —
    e.g. a Chain's own ".next" chain vs. a flat asset file."""
    entries = sorted(path.iterdir(), key=lambda entry: entry.name)
    return [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries]


def list_dir_tree(path: Path, _prefix: str = "") -> list[str]:
    """Recursive raw `ls -r` view for a '('/'@' target — same trailing
    "/" convention as list_dir(), but descending into every subdirectory
    too, each already indented four spaces per nesting level so the
    command layer can just print the lines as given."""
    lines = []
    for entry in sorted(path.iterdir(), key=lambda entry: entry.name):
        if entry.is_dir():
            lines.append(f"{_prefix}{entry.name}/")
            lines.extend(list_dir_tree(entry, _prefix + "    "))
        else:
            lines.append(f"{_prefix}{entry.name}")
    return lines
