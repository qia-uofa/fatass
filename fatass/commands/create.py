import argparse
import sys

from .._internal.prompts import load_topology_edit_system_prompt
from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE
from ..core.node import Node
from ..core.node_list import NodeList
from ..errors import FreeError, TopologyValidationError
from ..topology_ops.scaffold import create_node, create_transform, refine_node, refine_transform
from ._targets import parse_create_target
from .base import Command

_BASE_CLASSES: dict[str, type[Node]] = {"Node": Node, "NodeList": NodeList}


class CreateCommand(Command):
    name = "create"
    help = "scaffold a node or transform if it doesn't exist yet"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help=(
                "node.path, or <transform>@<node.path> to create a transform; "
                "a node.path may end with (NodeSubclass) (e.g. "
                "\"members(NodeList)\") to subclass fatass.<NodeSubclass> "
                "instead of fatass.Node"
            ),
        )
        parser.add_argument(
            "--prompt", help="after creating, use the Claude CLI to flesh it out"
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
        try:
            node_path, transform_name, base_class = parse_create_target(args.target)
            if base_class not in _BASE_CLASSES:
                raise ValueError(
                    f"unknown NodeSubclass {base_class!r} "
                    f"(expected one of {sorted(_BASE_CLASSES)})"
                )
            if transform_name is not None:
                if base_class != "Node":
                    raise ValueError(
                        f"(NodeSubclass) only applies to creating a node, not a "
                        f"transform: {args.target!r}"
                    )
                created = create_transform(node_path, transform_name)
                label = f"{node_path}.transforms.{transform_name}"
                if created and args.prompt:
                    refine_transform(
                        node_path,
                        transform_name,
                        args.prompt,
                        system_prompt=load_topology_edit_system_prompt("create"),
                        permission_mode=args.permission_mode,
                        silent=args.silent,
                        model=args.model,
                        tools=args.tools,
                    )
            else:
                created = create_node(node_path, base_class)
                label = node_path
                if created and args.prompt:
                    refine_node(
                        node_path,
                        args.prompt,
                        system_prompt=load_topology_edit_system_prompt(
                            "create", extra=_BASE_CLASSES[base_class].create_sys_prompt()
                        ),
                        permission_mode=args.permission_mode,
                        silent=args.silent,
                        model=args.model,
                        tools=args.tools,
                    )
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
