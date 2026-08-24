import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.archive import archive_topology
from ._targets import resolve_node_path
from .base import Command


class ArchiveCommand(Command):
    name = "archive"
    help = "move the current topology/home trees under ./archive/ and start fresh"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "name",
            nargs="?",
            default=None,
            help="label prefixed to the archive's timestamp (default: timestamp only)",
        )
        parser.add_argument(
            "--node",
            default=None,
            help=(
                "archive only this node.path's own subtree instead of the whole "
                "topology; the rest of the topology is left untouched (no fresh "
                "reset)"
            ),
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path = resolve_node_path(args.node) if args.node else None
            dir_name = archive_topology(args.name, node_path=node_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if node_path:
            print(f"archived {node_path} to archive/{dir_name}")
        else:
            print(f"archived to archive/{dir_name}, topology and home are now empty")
        return 0
