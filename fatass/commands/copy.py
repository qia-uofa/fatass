import argparse
import sys

from ..errors import TopologyValidationError
from ..scaffold import copy_node
from ._targets import resolve_node_path
from .base import Command


class CopyCommand(Command):
    name = "copy"
    help = "copy a node (and its nested nodes) to a new path"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("old_path", help="source node.path")
        parser.add_argument("new_path", help="destination node.path")

    def run(self, args: argparse.Namespace) -> int:
        try:
            old_path = resolve_node_path(args.old_path)
            new_path = resolve_node_path(args.new_path)
            updated = copy_node(old_path, new_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{old_path}: copied to {new_path}")
        if updated:
            print(f"{updated} file(s) had references rewritten")
        return 0
