import argparse
import sys
from pathlib import Path

from ..errors import TopologyValidationError
from ..graph import write_graph
from ._targets import resolve_node_path
from .base import Command


class GraphCommand(Command):
    name = "graph"
    help = "write a UML diagram of node inclusion and transform dependencies"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "node_path",
            nargs="?",
            default=None,
            help="node.path to use as the graph's root (default: whole topology)",
        )
        parser.add_argument(
            "-o",
            "--output",
            default=None,
            help="output file path (default: ./<root>.puml, or ./topology.puml with no node given)",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            root = resolve_node_path(args.node_path) if args.node_path is not None else None
            output = Path(args.output) if args.output is not None else None
            output_path = write_graph(output, root)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"wrote graph to {output_path}")
        return 0
