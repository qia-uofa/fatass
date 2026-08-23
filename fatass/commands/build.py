import argparse
import sys

from ..errors import TopologyValidationError
from ..transform import apply_transform
from ._targets import parse_kv_args, resolve_node_path
from .base import Command


class BuildCommand(Command):
    name = "build"
    help = "shorthand for `apply build@<node.path>`"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path")
        parser.add_argument(
            "args", nargs="*", help="key=value context arguments for the transform"
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path = resolve_node_path(args.node_path)
            context = parse_kv_args(args.args)
            apply_transform(node_path, "build", context)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{node_path}.transforms.build: applied")
        return 0
