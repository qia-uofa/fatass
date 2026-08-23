from .adhoc import free_at
from .archive import archive_topology, retrieve_topology
from .errors import FreeCoercionError, FreeError, TopologyValidationError

# `from .free import free` rebinds this package's `free` attribute to the
# function, shadowing the `fatass.free` *submodule* for any attribute-based
# access to it (`import fatass.free as x`, `fatass.free.<anything>`) —
# `importlib.import_module("fatass.free")` still gets the module. Same
# reasoning ruled out naming anything else in fatass/*.py after its own
# public re-export (see archive_topology/retrieve_topology below) — `free`
# is grandfathered in since it's the whole point of the package's name.
from .free import free, free_topology
from .node import Node
from .purge import purge_node
from .scaffold import (
    copy_node,
    create_node,
    create_transform,
    move_node,
    refine_node,
    refine_transform,
    remove_node,
    remove_transform,
)
from .transform import apply_transform, discover, run_transform

# Imported last: node.py files under topology/ do `import fatass` and
# subclass `fatass.Node`, so Node (and free, etc.) must already be defined
# on this module by the time topology/ is imported.
from . import topology

__all__ = [
    "Node",
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
