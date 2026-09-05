from .core.adhoc import free_at
from .core.free import free, free_topology
from .node.node import Node
from .node.chain import Chain
from .node.single import Single, SingleTxt, SinglePdf, SingleMd, SingleJson, SingleCsv
from .node.array import Array, ArrayTxt, ArrayPdf, ArrayMd, ArrayJson, ArrayCsv
from .node.tuple import Tuple
from .node.repo import Repo
from .core.transform import apply_transform, discover, run_transform
from .errors import FreeCoercionError, FreeError, TopologyValidationError
from .topology_ops.archive import archive_topology, retrieve_topology
from .topology_ops.purge import purge_node
from .topology_ops.scaffold import (
    copy_node,
    create_node,
    create_transform,
    move_node,
    refine_node,
    refine_transform,
    remove_node,
    remove_transform,
)

__all__ = [
    "Node",
    "Chain",
    "Single",
    "SingleTxt",
    "SinglePdf",
    "SingleMd",
    "SingleJson",
    "SingleCsv",
    "Array",
    "ArrayTxt",
    "ArrayPdf",
    "ArrayMd",
    "ArrayJson",
    "ArrayCsv",
    "Tuple",
    "Repo",
    "free",
    "free_topology",
    "run_transform",
    "apply_transform",
    "discover",
    "create_node",
    "create_transform",
    "refine_node",
    "refine_transform",
    "move_node",
    "copy_node",
    "remove_node",
    "remove_transform",
    "purge_node",
    "free_at",
    "archive_topology",
    "retrieve_topology",
    "topology",
    "TopologyValidationError",
    "FreeError",
    "FreeCoercionError",
]


def _register_framework_node_classes(cls: type[Node]) -> None:
    """Exposes every `fatass.node.*`-defined `Node` subclass (Single/Array
    and their typed variants) as `fatass.<ClassName>`, even ones not
    explicitly imported above -- a generated node class body always reads
    as `fatass.<base_class>` (see topology_ops/scaffold.py), so a subclass
    that `create`'s programmatic discovery (commands/create.py) accepts as
    a `(NodeSubclass)` target must actually be reachable here too, without
    a matching import having to be added by hand each time."""
    for sub in cls.__subclasses__():
        if sub.__module__.startswith(f"{__name__}.node.") and sub.__name__ not in __all__:
            globals()[sub.__name__] = sub
            __all__.append(sub.__name__)
        _register_framework_node_classes(sub)


_register_framework_node_classes(Node)
del _register_framework_node_classes

# Imported last: each node's own file under topology/ does `import fatass`
# and subclasses `fatass.Node`, so Node (and free, etc.) must already be
# defined on this module by the time topology/ is imported.
from . import topology  # noqa: E402
