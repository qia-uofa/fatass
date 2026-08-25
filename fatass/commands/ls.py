import argparse
import sys

from ..errors import TopologyValidationError
from ..ls import list_dir, list_node, list_root
from ..resolve.cwd import ROOT, expand
from ..resolve.targets import resolve as resolve_target
from .base import Command


class LsCommand(Command):
    name = "ls"
    help = "list a node's subnodes and transforms, or (for a ':'/'@' target) its directory content"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            nargs="?",
            default=".",
            help="node.path (subnodes + transforms) | node.path:rel/path or "
            "transform@node.path (raw directory listing); defaults to the "
            "current node ('.'), which lists all top-level nodes if no "
            "current node is set",
        )

    def run(self, args: argparse.Namespace) -> int:
        is_raw = ":" in args.target or "@" in args.target
        try:
            if is_raw:
                names = list_dir(resolve_target(args.target))
            else:
                node_path = expand(args.target)
                if node_path == ROOT:
                    subnodes, transforms = list_root(), []
                else:
                    subnodes, transforms = list_node(node_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if is_raw:
            for name in names:
                print(name)
            return 0

        if not subnodes and not transforms:
            print("(empty)")
            return 0

        for name in subnodes:
            print(f"{name}/")
        for spec in transforms:
            deps = ", ".join(spec.dependencies) if spec.dependencies else "no input"
            print(f"{spec.name}@ ({deps})")
        return 0
