import argparse
import sys

from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ..core.transform import run_transform
from ._targets import parse_node_path
from .base import Command


class RunCommand(Command):
    name = "run"
    help = "run one or more transforms"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("path", help="node.path or node.path.transforms.<name>")
        parser.add_argument("--force", action="store_true", help="bypass the cache")

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_node_path(args.path)
            results = run_transform(node_path, transform_name, force=args.force)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        display = pascal_node_path(node_path)
        if not results:
            print(f"no transforms found under {display}")
            return 0

        for name, ran in results.items():
            status = "ran" if ran else "skipped (cache hit)"
            print(f"{display}.transforms.{name}: {status}")
        return 0
