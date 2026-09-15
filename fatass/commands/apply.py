import argparse
import sys

from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ..core.transform import apply_transform
from ._targets import parse_kv_args, parse_transform_target
from .base import Command


class ApplyCommand(Command):
    name = "apply"
    help = "run one transform with explicit arguments, ignoring the cache"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target", help="Node.transform, e.g. ExampleB.synthesize"
        )
        parser.add_argument(
            "args", nargs="*", help="key=value context arguments for the transform"
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_transform_target(args.target)
            context = parse_kv_args(args.args)
            apply_transform(node_path, transform_name, context)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{pascal_node_path(node_path)}.transforms.{transform_name}: applied")
        return 0
