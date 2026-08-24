import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.archive import retrieve_node, retrieve_topology
from ._targets import resolve_node_path
from .base import Command


class RetrieveCommand(Command):
    name = "retrieve"
    help = "restore an archived topology/home snapshot from ./archive/"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "name",
            nargs="?",
            default=None,
            help="label of the archive to restore (default: toggle the latest unnamed archive)",
        )
        parser.add_argument(
            "--node",
            default=None,
            help=(
                "restore only this node.path from the named archive, back to its "
                "original location, instead of the whole snapshot (requires "
                "`name`)"
            ),
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            if args.node:
                if not args.name:
                    raise TopologyValidationError("--node requires a named archive")
                node_path = resolve_node_path(args.node)
                dir_name = retrieve_node(args.name, node_path)
            else:
                node_path = None
                dir_name = retrieve_topology(args.name)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if node_path:
            print(f"retrieved {node_path} from archive/{dir_name}")
        else:
            print(f"retrieved archive/{dir_name}")
        return 0
