import argparse
import sys

from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ..topology_ops.bind import unbind_transform
from ._targets import parse_transform_target, resolve_and_validate_node_path
from .base import Command


class UnbindCommand(Command):
    name = "unbind"
    help = "remove one or more nodes from a transform's declared Node-typed dependencies"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="Node.transform")
        parser.add_argument(
            "deps", nargs="+", help="one or more node.path arguments to unbind"
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_transform_target(args.target)
            dep_paths = [resolve_and_validate_node_path(d) for d in args.deps]
            unbound = unbind_transform(node_path, transform_name, dep_paths)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        label = f"{pascal_node_path(node_path)}.transforms.{transform_name}"
        print(f"{label}: unbound {', '.join(pascal_node_path(p) for p in unbound)}")
        return 0
