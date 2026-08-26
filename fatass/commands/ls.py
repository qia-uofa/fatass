import argparse
import sys

from ..errors import TopologyValidationError
from ..ls import (
    NodeSummary,
    NodeTree,
    list_dir,
    list_dir_tree,
    list_node,
    list_node_tree,
    list_root,
    list_root_tree,
)
from ..resolve.cwd import ROOT, expand
from ..resolve.targets import resolve as resolve_target
from .base import Command


def _render_node(summary: NodeSummary) -> list[str]:
    """Render a node's own class + subnodes (`name : ClassName(...)`,
    "this is the node" — bare own name, it's obviously *this* node), then
    each of its transforms (`name = transform(...)`, "this is how it's
    built") as a call whose arguments are each dependency's own
    `~.<full path> : ClassName(<children>)` — same "this is a node" `:`
    shape, but full-path-addressed since a dependency can live anywhere
    in the topology, so a dependency's shape is visible without a
    separate `ls` call."""
    own_name = summary.path.rsplit(".", 1)[-1]
    lines = [f"{own_name} : {summary.class_name}({', '.join(summary.children)})"]

    for spec in summary.transforms:
        if not spec.dependencies:
            lines.append(f"{own_name} = {spec.name}()")
            continue
        lines.append(f"{own_name} = {spec.name}(")
        for dep in spec.dependencies:
            dep_args = ", ".join(dep.children)
            lines.append(f"    ~.{dep.path} : {dep.class_name}({dep_args}),")
        lines.append(")")

    return lines


def _render_node_tree(tree: NodeTree, indent: str = "") -> list[str]:
    """Render the full inclusion tree (`fatass ls -r`) the same
    `name : ClassName(...)` way as `_render_node`'s own line, but with
    each child recursively expanded in place — one nested block per
    child, comma-terminated — instead of a flat list of bare names."""
    own_name = "~" if not tree.path else tree.path.rsplit(".", 1)[-1]

    if not tree.children:
        return [f"{indent}{own_name} : {tree.class_name}()"]

    lines = [f"{indent}{own_name} : {tree.class_name}("]
    for child in tree.children:
        lines.extend(_render_node_tree(child, indent + "    "))
        lines[-1] += ","
    lines.append(f"{indent})")
    return lines


class LsCommand(Command):
    name = "ls"
    help = "list a node's own class, subnodes, and transforms, or (for a ':'/'@' target) its directory content"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            nargs="?",
            default=".",
            help="node.path (class + subnodes + transforms) | node.path:rel/path or "
            "transform@node.path (raw directory listing); defaults to the "
            "current node ('.'), which lists all top-level nodes if no "
            "current node is set",
        )
        parser.add_argument(
            "-r",
            action="store_true",
            help="recurse — show the full inclusion tree (or, for a ':'/'@' "
            "target, the full directory tree) instead of just one level",
        )

    def run(self, args: argparse.Namespace) -> int:
        is_raw = ":" in args.target or "@" in args.target
        try:
            if is_raw:
                target_dir = resolve_target(args.target)
                names = list_dir_tree(target_dir) if args.r else list_dir(target_dir)
            else:
                node_path = expand(args.target)
                if args.r:
                    tree = list_root_tree() if node_path == ROOT else list_node_tree(node_path)
                elif node_path != ROOT:
                    summary = list_node(node_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if is_raw:
            for name in names:
                print(name)
            return 0

        if args.r:
            for line in _render_node_tree(tree):
                print(line)
            return 0

        if node_path == ROOT:
            print(f"~ : topology({', '.join(list_root())})")
            return 0

        for line in _render_node(summary):
            print(line)
        return 0
