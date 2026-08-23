import argparse
import sys

from ..errors import FreeError, TopologyValidationError
from ..scaffold import refine_node, refine_transform
from ._targets import parse_maybe_at_target
from .base import Command


class ModifyCommand(Command):
    name = "modify"
    help = "edit an existing node's class file or transform file with a prompt"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target", help="node.path, or <transform>@<node.path> to target a transform file"
        )
        parser.add_argument("--prompt", required=True, help="what the agent should do")

    def run(self, args: argparse.Namespace) -> int:
        node_path, transform_name = parse_maybe_at_target(args.target)
        try:
            if transform_name is not None:
                refine_transform(node_path, transform_name, args.prompt)
                label = f"{node_path}.transforms.{transform_name}"
            else:
                refine_node(node_path, args.prompt)
                label = node_path
        except (TopologyValidationError, FreeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{label}: modified")
        return 0
