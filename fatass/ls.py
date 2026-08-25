import dataclasses
from pathlib import Path

from .core.transform import discover
from .errors import TopologyValidationError
from .topology_ops.scaffold import _all_node_paths, _node_dir


@dataclasses.dataclass
class TransformInfo:
    name: str
    dependencies: list[str]
    """Topology paths of the transform's Node-typed parameters, in
    declaration order — empty for a transform with no such dependency."""


def list_root() -> list[str]:
    """Top-level node names directly under fatass/topology/ — the listing
    for the true topology root (FATASS_NODE unset / expanded to "~"),
    which has no node file of its own and thus no transforms."""
    return sorted(path for path in _all_node_paths() if "." not in path)


def list_node(node_path: str) -> tuple[list[str], list[TransformInfo]]:
    """(direct subnode names, transforms with their input node paths) for
    node_path — the structured `fatass ls <node.path>` view. Subnodes are
    just the next path segment (e.g. "b" for "a.b" under "a"), not full
    paths; nested descendants aren't included."""
    if not _node_dir(node_path).is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    prefix = node_path + "."
    subnodes = sorted(
        path[len(prefix) :]
        for path in _all_node_paths()
        if path.startswith(prefix) and "." not in path[len(prefix) :]
    )

    transforms = [
        TransformInfo(
            name=spec.name,
            dependencies=[dep_cls._topology_path() for dep_cls in spec.dependencies.values()],
        )
        for spec in discover(node_path)
    ]
    return subnodes, transforms


def list_dir(path: Path) -> list[str]:
    """Directory entry names, sorted — the raw `ls` view used for a ':'
    (home/ asset directory) target."""
    return sorted(entry.name for entry in path.iterdir())
