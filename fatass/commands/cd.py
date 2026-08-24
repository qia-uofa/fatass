import argparse
import sys

from ..errors import TopologyValidationError
from ..resolve.cwd import ROOT, expand, write_current_node
from ..topology_ops.scaffold import _node_dir
from .base import Command


class CdCommand(Command):
    name = "cd"
    help = "change the current node (FATASS_NODE) that relative targets resolve against"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help="node.path relative to the current node, '.', '..', or '~...' for an absolute path",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path = expand(args.target)
            if node_path != ROOT and not _node_dir(node_path).is_dir():
                raise TopologyValidationError(f"no node at {node_path!r}")
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        write_current_node(node_path)
        print(node_path)
        return 0
