import argparse
import sys

from ..archive import retrieve_topology
from ..errors import TopologyValidationError
from .base import Command


class RetrieveCommand(Command):
    name = "retrieve"
    help = "restore an archived topology/nodes snapshot from ./archive/"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "name",
            nargs="?",
            default=None,
            help="label of the archive to restore (default: toggle the latest unnamed archive)",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            dir_name = retrieve_topology(args.name)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"retrieved archive/{dir_name}")
        return 0
