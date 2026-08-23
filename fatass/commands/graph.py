import argparse
from pathlib import Path

from ..graph import write_graph
from .base import Command


class GraphCommand(Command):
    name = "graph"
    help = "write a UML diagram of node inclusion and transform dependencies"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-o",
            "--output",
            default="./graph.uml",
            help="output file path (default: ./graph.uml)",
        )

    def run(self, args: argparse.Namespace) -> int:
        output_path = write_graph(Path(args.output))
        print(f"wrote graph to {output_path}")
        return 0
