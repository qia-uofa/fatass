import argparse
import sys

from ..errors import TopologyValidationError
from ._targets import resolve_chain
from .base import Command


class PopCommand(Command):
    name = "pop"
    help = "remove a Chain's tail item, or item n if given"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Chain")
        parser.add_argument(
            "n",
            nargs="?",
            type=int,
            default=None,
            help="index to remove (default: the tail — length() - 1)",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            list_cls = resolve_chain(args.node_path)
            index = args.n if args.n is not None else list_cls.length() - 1
            list_cls.pop(args.n)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{list_cls._topology_path()}: popped item {index}")
        return 0
