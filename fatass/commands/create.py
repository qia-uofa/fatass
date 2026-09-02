import argparse
import sys

from ..core.node import Node
from ..core.chain import Chain
from ..errors import TopologyValidationError
from ..topology_ops.bind import add_plain_params, bind_transform
from ..topology_ops.scaffold import create_node, create_transform
from ._targets import parse_create_target
from .base import Command

_BASE_CLASSES: dict[str, type[Node]] = {"Node": Node, "Chain": Chain}


class CreateCommand(Command):
    name = "create"
    help = "scaffold a node or transform if it doesn't exist yet"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help=(
                "node.path, or <transform>@<node.path> to create a transform "
                "(optionally with dependency node.paths and/or plain "
                "name:type parameters in parens, e.g. "
                "\"build(node1,node2,prompt:str,n:int)@node\"); a node.path "
                "may end with (NodeSubclass) (e.g. \"members(Chain)\") to "
                "subclass fatass.<NodeSubclass> instead of fatass.Node"
            ),
        )

    def run(self, args: argparse.Namespace) -> int:
        bound: list[str] = []
        added_params: list[str] = []
        try:
            node_path, transform_name, base_class, dep_paths, plain_params = (
                parse_create_target(args.target)
            )
            if base_class not in _BASE_CLASSES:
                raise ValueError(
                    f"unknown NodeSubclass {base_class!r} "
                    f"(expected one of {sorted(_BASE_CLASSES)})"
                )
            if transform_name is not None:
                if base_class != "Node":
                    raise ValueError(
                        f"(NodeSubclass) only applies to creating a node, not a "
                        f"transform: {args.target!r}"
                    )
                created = create_transform(node_path, transform_name)
                label = f"{node_path}.transforms.{transform_name}"
                if created and dep_paths:
                    bound = bind_transform(node_path, transform_name, dep_paths)
                if created and plain_params:
                    added_params = add_plain_params(node_path, transform_name, plain_params)
            else:
                created = create_node(node_path, base_class)
                label = node_path
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{label}: already exists" if not created else f"{label}: created")
        if bound:
            print(f"{label}: bound {', '.join(bound)}")
        if added_params:
            print(f"{label}: added parameters {', '.join(added_params)}")
        return 0
