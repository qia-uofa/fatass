import argparse
import sys

from ..errors import TopologyValidationError
from ._targets import resolve_chain
from .base import Command


class LenCommand(Command):
    name = "len"
    help = "print a Chain's current length"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Chain")

    def run(self, args: argparse.Namespace) -> int:
        try:
            list_cls = resolve_chain(args.node_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(list_cls.length())
        return 0
