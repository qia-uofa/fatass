import argparse
import sys

from ..adhoc import free_at
from ..errors import FreeError
from .base import Command


class FreeCommand(Command):
    name = "free"
    help = "invoke the Claude CLI directly inside a nodes/ or topology/ dir"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="nodes.<path> or topology.<path>")
        parser.add_argument("--prompt", required=True, help="what the agent should do")

    def run(self, args: argparse.Namespace) -> int:
        try:
            free_at(args.target, args.prompt)
        except (ValueError, FreeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{args.target}: done")
        return 0
