import argparse
import sys

from ..errors import TopologyValidationError
from ..transform import run_transform
from ._targets import parse_node_path
from .base import Command


class RunCommand(Command):
    name = "run"
    help = "run one or more transforms"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("path", help="node.path or node.path.transforms.<name>")
        parser.add_argument("--force", action="store_true", help="bypass the cache")

    def run(self, args: argparse.Namespace) -> int:
        node_path, transform_name = parse_node_path(args.path)
        try:
            results = run_transform(node_path, transform_name, force=args.force)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if not results:
            print(f"no transforms found under {node_path}")
            return 0

        for name, ran in results.items():
            status = "ran" if ran else "skipped (cache hit)"
            print(f"{node_path}.transforms.{name}: {status}")
        return 0
