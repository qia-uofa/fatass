import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.bind import bind_transform
from ._targets import parse_at_target, resolve_node_path
from .base import Command


class BindCommand(Command):
    name = "bind"
    help = "add one or more nodes as declared Node-typed dependencies on a transform"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="<transform>@<node.path>")
        parser.add_argument(
            "deps", nargs="+", help="one or more node.path arguments to bind as inputs"
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_at_target(args.target)
            dep_paths = [resolve_node_path(d) for d in args.deps]
            bound = bind_transform(node_path, transform_name, dep_paths)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        label = f"{transform_name}@{node_path}"
        if bound:
            print(f"{label}: bound {', '.join(bound)}")
        skipped = [d for d in dep_paths if d not in bound]
        if skipped:
            print(f"{label}: already bound {', '.join(skipped)}")
        return 0
