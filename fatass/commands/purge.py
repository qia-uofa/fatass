import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.purge import purge_node
from .base import Command


class PurgeCommand(Command):
    name = "purge"
    help = "remove a node's own content from home/ (not its subnode directories)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path")
        parser.add_argument(
            "-rs", action="store_true", help="also purge every subnode, recursively"
        )
        parser.add_argument(
            "-rd",
            action="store_true",
            help="also purge every dependency node, recursively",
        )
        parser.add_argument(
            "-rsd",
            action="store_true",
            help=(
                "purge subnodes and dependency nodes together, recursively, "
                "in one combined traversal (not -rs then -rd separately — "
                "see blueprint/command/README.md)"
            ),
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            result = purge_node(args.node_path, rs=args.rs, rd=args.rd, rsd=args.rsd)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        for node_path in sorted(result):
            count = result[node_path]
            noun = "entry" if count == 1 else "entries"
            print(f"{node_path}: purged {count} {noun}")

        total = sum(result.values())
        print(f"purged {total} entries across {len(result)} node(s)")
        return 0
