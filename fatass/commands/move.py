import argparse
import sys

from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ..topology_ops.scaffold import move_node
from ._targets import resolve_and_validate_node_path, resolve_move_target
from .base import Command


class MoveCommand(Command):
    name = "move"
    help = "move a node (and its nested nodes) to a new path, renaming it"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "old_path",
            help="current node.path, optionally suffixed with "
            "<NodeType(args)> (e.g. 'foo.bar<Chain>') to assert its type",
        )
        parser.add_argument(
            "target",
            help="destination node.path (not yet existing — move_node "
            "itself raises if something is already there) — a trailing "
            "'*' segment (e.g. 'node2.*') keeps old_path's own name, just "
            "reparented under node2, same as Unix `mv file dir/`",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            old_path = resolve_and_validate_node_path(args.old_path)
            new_path = resolve_move_target(args.target, old_path)
            updated = move_node(old_path, new_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{pascal_node_path(old_path)}: moved to {pascal_node_path(new_path)}")
        if updated:
            print(f"{updated} file(s) had references rewritten")
        return 0
