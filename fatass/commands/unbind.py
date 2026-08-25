import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.bind import unbind_transform
from ._targets import parse_at_target, resolve_node_path
from .base import Command


class UnbindCommand(Command):
    name = "unbind"
    help = "remove one or more nodes from a transform's declared Node-typed dependencies"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="<transform>@<node.path>")
        parser.add_argument(
            "deps", nargs="+", help="one or more node.path arguments to unbind"
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_at_target(args.target)
            dep_paths = [resolve_node_path(d) for d in args.deps]
            unbound = unbind_transform(node_path, transform_name, dep_paths)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        label = f"{transform_name}@{node_path}"
        print(f"{label}: unbound {', '.join(unbound)}")
        return 0
