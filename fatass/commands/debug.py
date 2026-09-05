import argparse
import sys

from .._internal.prompts import load_topology_edit_system_prompt
from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE, NO_PROMPT_TEXT
from ..errors import FreeError, TopologyValidationError
from ..topology_ops.scaffold import debug_transform
from ._targets import parse_at_target
from .base import Command


class DebugCommand(Command):
    name = "debug"
    help = "prompt the agent to debug a failing transform, with log history and its own output as context"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="<transform>@<node.path> to debug")
        parser.add_argument(
            "prompt",
            nargs="?",
            default="",
            help="what's going wrong / what to focus on; omitted or an empty "
            f"string is passed through as the literal text {NO_PROMPT_TEXT!r}, "
            "since the agent needs some message",
        )
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

    def run(self, args: argparse.Namespace) -> int:
        prompt = args.prompt if args.prompt else NO_PROMPT_TEXT
        try:
            node_path, transform_name = parse_at_target(args.target)
            summary = debug_transform(
                node_path,
                transform_name,
                prompt,
                system_prompt=load_topology_edit_system_prompt("debug"),
                permission_mode=args.permission_mode,
                silent=args.silent,
                model=args.model,
                tools=args.tools,
            )
        except (TopologyValidationError, FreeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if summary:
            print(summary)
        print(f"{node_path}.transforms.{transform_name}: debugged")
        return 0
