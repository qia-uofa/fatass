import argparse
import subprocess
import sys

from ..errors import TopologyValidationError
from ..resolve.targets import resolve as resolve_target
from .base import Command


class ShCommand(Command):
    name = "sh"
    help = "run a shell command with its cwd resolved from a node, transform, or file target"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help="node.path | transform@node.path | node.path(relative/file/path)",
        )
        parser.add_argument(
            "command", nargs=argparse.REMAINDER, help="shell command to run"
        )

    def run(self, args: argparse.Namespace) -> int:
        if not args.command:
            print("error: no command given", file=sys.stderr)
            return 1

        try:
            cwd = resolve_target(args.target)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        result = subprocess.run(" ".join(args.command), shell=True, cwd=cwd)
        return result.returncode
