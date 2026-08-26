import argparse
import sys

from ..core.adhoc import free_at
from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE
from ..errors import FreeError, TopologyValidationError
from .base import Command


class FreeCommand(Command):
    name = "free"
    help = "invoke the Claude CLI directly inside a node/transform/file target's directory"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help="node.path | transform@node.path | node.path:relative/file/path",
        )
        parser.add_argument("--prompt", required=True, help="what the agent should do")
        parser.add_argument(
            "--silent",
            action="store_true",
            help="run the agent call headlessly instead of opening a live conversation",
        )
        parser.add_argument(
            "--permission-mode",
            default=DEFAULT_PERMISSION_MODE,
            help=f"Claude CLI --permission-mode to use (default: {DEFAULT_PERMISSION_MODE})",
        )
        parser.add_argument(
            "--model",
            default=None,
            help="Claude CLI --model to use (default: whatever `claude` is already configured with)",
        )
        parser.add_argument(
            "--tools",
            default=DEFAULT_ALLOWED_TOOLS,
            help=f"Claude CLI --allowedTools to use (default: {DEFAULT_ALLOWED_TOOLS})",
        )
        parser.add_argument(
            "--effort",
            default=None,
            choices=["low", "medium", "high", "xhigh", "max"],
            help="Claude CLI --effort to use (default: whatever `claude` is already configured with)",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            free_at(
                args.target,
                args.prompt,
                permission_mode=args.permission_mode,
                silent=args.silent,
                model=args.model,
                tools=args.tools,
                effort=args.effort,
            )
        except (TopologyValidationError, FreeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{args.target}: done")
        return 0
