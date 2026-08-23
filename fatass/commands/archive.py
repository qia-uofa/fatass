import argparse
import sys

from ..archive import archive_topology
from ..errors import TopologyValidationError
from .base import Command


class ArchiveCommand(Command):
    name = "archive"
    help = "move the current topology/nodes trees under ./archive/ and start fresh"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "name",
            nargs="?",
            default=None,
            help="label prefixed to the archive's timestamp (default: timestamp only)",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            dir_name = archive_topology(args.name)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"archived to archive/{dir_name}, topology and nodes are now empty")
        return 0
