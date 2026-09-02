import argparse
import sys

from ..errors import TopologyValidationError
from ._targets import resolve_chain
from .base import Command


class PushCommand(Command):
    name = "push"
    help = "append one item to a Chain, seeded as a copy of the dummy head's own content"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Chain")

    def run(self, args: argparse.Namespace) -> int:
        try:
            list_cls = resolve_chain(args.node_path)
            index = list_cls.length()
            list_cls.insert(index)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{list_cls._topology_path()}: pushed item {index}")
        return 0
