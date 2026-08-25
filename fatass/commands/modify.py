import argparse
import sys

from .._internal.prompts import load_topology_edit_system_prompt
from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE
from ..core.transform import _import_node
from ..errors import FreeError, TopologyValidationError
from ..topology_ops.scaffold import refine_node, refine_transform
from ._targets import parse_maybe_at_target
from .base import Command


class ModifyCommand(Command):
    name = "modify"
    help = "edit an existing node's class file or transform file with a prompt"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target", help="node.path, or <transform>@<node.path> to target a transform file"
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

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path, transform_name = parse_maybe_at_target(args.target)
            if transform_name is not None:
                refine_transform(
                    node_path,
                    transform_name,
                    args.prompt,
                    system_prompt=load_topology_edit_system_prompt("modify"),
                    permission_mode=args.permission_mode,
                    silent=args.silent,
                    model=args.model,
                    tools=args.tools,
                )
                label = f"{node_path}.transforms.{transform_name}"
            else:
                try:
                    # Best-effort: the node's own file might currently be
                    # broken (e.g. the very thing this modify call is
                    # meant to fix), in which case importing it for its
                    # class-specific prompt hook isn't worth failing the
                    # command over.
                    extra = _import_node(node_path).modify_sys_prompt()
                except Exception:
                    extra = None
                refine_node(
                    node_path,
                    args.prompt,
                    system_prompt=load_topology_edit_system_prompt("modify", extra=extra),
                    permission_mode=args.permission_mode,
                    silent=args.silent,
                    model=args.model,
                    tools=args.tools,
                )
                label = node_path
        except (TopologyValidationError, FreeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{label}: modified")
        return 0
