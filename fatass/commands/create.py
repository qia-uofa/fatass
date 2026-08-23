import argparse
import sys

from ..errors import FreeError, TopologyValidationError
from ..scaffold import create_node, create_transform, refine_node, refine_transform
from ._targets import parse_maybe_at_target
from .base import Command


class CreateCommand(Command):
    name = "create"
    help = "scaffold a node or transform if it doesn't exist yet"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target", help="node.path, or <transform>@<node.path> to create a transform"
        )
        parser.add_argument(
            "--prompt", help="after creating, use the Claude CLI to flesh it out"
        )

    def run(self, args: argparse.Namespace) -> int:
        node_path, transform_name = parse_maybe_at_target(args.target)
        try:
            if transform_name is not None:
                created = create_transform(node_path, transform_name)
                label = f"{node_path}.transforms.{transform_name}"
                if created and args.prompt:
                    refine_transform(node_path, transform_name, args.prompt)
            else:
                created = create_node(node_path)
                label = node_path
                if created and args.prompt:
                    refine_node(node_path, args.prompt)
        except (TopologyValidationError, FreeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if not created:
            print(f"{label}: already exists")
        elif args.prompt:
            print(f"{label}: created, refined with prompt")
        else:
            print(f"{label}: created")
        return 0
