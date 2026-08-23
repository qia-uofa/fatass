import argparse
import sys

from ..errors import TopologyValidationError
from ..scaffold import move_node
from .base import Command


class MoveCommand(Command):
    name = "move"
    help = "move a node (and its nested nodes) to a new path, renaming it"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("old_path", help="current node.path")
        parser.add_argument("new_path", help="destination node.path")

    def run(self, args: argparse.Namespace) -> int:
        try:
            updated = move_node(args.old_path, args.new_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{args.old_path}: moved to {args.new_path}")
        if updated:
            print(f"{updated} file(s) had references rewritten")
        return 0
