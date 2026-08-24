import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.scaffold import remove_node, remove_transform
from ._targets import parse_maybe_at_target
from .base import Command


class RemoveCommand(Command):
    name = "remove"
    help = "remove a node (and its nested nodes), or a single transform"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help="node.path to remove, or <transform>@<node.path> to remove just a transform",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_maybe_at_target(args.target)
            if transform_name is not None:
                remove_transform(node_path, transform_name)
                label = f"{node_path}.transforms.{transform_name}"
            else:
                remove_node(node_path)
                label = node_path
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{label}: removed")
        return 0
