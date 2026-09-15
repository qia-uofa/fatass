import argparse
import sys

from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ._targets import resolve_dictionary
from .base import Command


class DictSetCommand(Command):
    name = "set"
    group = "dict"
    help = "create a Dictionary key if it doesn't already exist (idempotent)"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Dictionary")
        parser.add_argument("key", help="the key to create")

    def run(self, args: argparse.Namespace) -> int:
        try:
            dict_cls = resolve_dictionary(args.node_path)
            already_present = args.key in dict_cls.keys()
            dict_cls.set(args.key)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        status = "already exists" if already_present else "created"
        print(f"{pascal_node_path(dict_cls._topology_path())}[{args.key}]: {status}")
        return 0
