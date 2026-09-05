import argparse
import sys

from .._internal.prompts import load_topology_edit_system_prompt
from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE, NO_PROMPT_TEXT
from ..core.transform import _import_node
from ..errors import FreeError, TopologyValidationError
from ..topology_ops.bind import bound_dep_paths
from ..topology_ops.scaffold import refine_node, refine_transform
from ._targets import parse_maybe_at_target
from .base import Command


def _node_sys_prompt(node_path: str) -> str | None:
    """Best-effort `modify_sys_prompt()` off `node_path`'s real class —
    None on import failure (e.g. the node's own file is currently broken)
    rather than failing the whole `modify` command over it."""
    try:
        return _import_node(node_path).modify_sys_prompt()
    except Exception:
        return None


def _transform_extra_sys_prompt(node_path: str, transform_name: str) -> str | None:
    """Extra system-prompt guidance for editing a transform: not just the
    transform's own node's class-specific conventions, but also each of its
    already-declared input dependencies' — a transform reading a `Single`/
    `Array`/`Chain` dependency needs to know that dependency's own access
    conventions just as much as it needs its own node's."""
    parts: list[str] = []
    for dep_path in bound_dep_paths(node_path, transform_name):
        dep_prompt = _node_sys_prompt(dep_path)
        if dep_prompt:
            parts.append(f"**Input dependency `{dep_path}`:**\n\n{dep_prompt}")
    owner_prompt = _node_sys_prompt(node_path)
    if owner_prompt:
        parts.append(f"**Output node `{node_path}` (this transform's own node):**\n\n{owner_prompt}")
    return "\n\n".join(parts) or None


class ModifyCommand(Command):
    name = "modify"
    help = "edit an existing node's class file or transform file with a prompt"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target", help="node.path, or <transform>@<node.path> to target a transform file"
        )
        parser.add_argument(
            "prompt",
            nargs="?",
            default="",
            help="what the agent should do; omitted or an empty string is passed "
            f"through as the literal text {NO_PROMPT_TEXT!r}, since the agent "
            "needs some message",
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
            node_path, transform_name = parse_maybe_at_target(args.target)
            if transform_name is not None:
                extra = _transform_extra_sys_prompt(node_path, transform_name)
                refine_transform(
                    node_path,
                    transform_name,
                    prompt,
                    system_prompt=load_topology_edit_system_prompt("modify", extra=extra),
                    permission_mode=args.permission_mode,
                    silent=args.silent,
                    model=args.model,
                    tools=args.tools,
                )
                label = f"{node_path}.transforms.{transform_name}"
            else:
                # Best-effort: the node's own file might currently be
                # broken (e.g. the very thing this modify call is meant
                # to fix), in which case importing it for its
                # class-specific prompt hook isn't worth failing the
                # command over -- handled inside _node_sys_prompt().
                extra = _node_sys_prompt(node_path)
                refine_node(
                    node_path,
                    prompt,
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
