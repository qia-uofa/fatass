import argparse
import sys

from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ._targets import resolve_dictionary
from .base import Command


class DictPopCommand(Command):
    name = "pop"
    group = "dict"
    help = "remove a Dictionary key outright — no other key is affected"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Dictionary")
        parser.add_argument("key", help="the key to remove")

    def run(self, args: argparse.Namespace) -> int:
        try:
            dict_cls = resolve_dictionary(args.node_path)
            dict_cls.pop(args.key)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{pascal_node_path(dict_cls._topology_path())}[{args.key}]: popped")
        return 0
