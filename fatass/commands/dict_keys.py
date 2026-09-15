import argparse
import sys

from ..errors import TopologyValidationError
from ._targets import resolve_dictionary
from .base import Command


class DictKeysCommand(Command):
    name = "keys"
    group = "dict"
    help = "list a Dictionary's current keys"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Dictionary")

    def run(self, args: argparse.Namespace) -> int:
        try:
            dict_cls = resolve_dictionary(args.node_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        for key in dict_cls.keys():
            print(key)
        return 0
