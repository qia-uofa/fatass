import argparse
import dataclasses
import sys

from .._internal.naming import pascal_case
from ..errors import TopologyValidationError
from ..ls import list_dir, list_dir_tree, list_root
from ..resolve.cwd import ROOT, expand
from ..resolve.targets import is_raw_target
from ..resolve.targets import resolve as resolve_target
from ..signature import (
    FULL_SIGNATURE,
    SIMPLE_TYPED_SIMPLE_STRUCTURED,
    _split_type_suffix,
    build_sig_data,
    render_signature,
    validate_node_signature,
)
from .base import Command

_NODE_SUMMARY_CONFIG = dataclasses.replace(SIMPLE_TYPED_SIMPLE_STRUCTURED, show_transforms=True)


def _render_node(node_path: str) -> list[str]:
    """Render a node's own full signature — real class name, base kind,
    direct subnodes, and its own transforms — via `fatass.signature`'s
    own "{...}" transforms-block grammar (see `FULL_SIGNATURE`), in the
    exact shape `touch` itself accepts back as input, so an `ls` output
    is directly reusable to recreate what it describes elsewhere. One
    dense line (matching this view's own long-standing single-line
    convention — `-r` is where pretty multi-line printing belongs).
    Each transform's own dependency is shown as its bare pathed identity
    ("@Foo.Bar") — `ls` that path directly for its own shape."""
    data = build_sig_data(node_path, max_depth=1, with_transforms=True)
    return render_signature(data, _NODE_SUMMARY_CONFIG).splitlines()


def _render_node_tree(node_path: str) -> str:
    """The full inclusion tree (`fatass ls -r <node.path>`) as one
    complete, recursively-typed-and-structured signature INCLUDING every
    node's own transforms (see `fatass.signature`'s `FULL_SIGNATURE`) —
    every subnode, all the way down, each with its own real class name,
    base kind, constructor arguments, and "{...}" transforms block.
    Pretty-printed (`pretty=True`) — one child/transform per line,
    indented by nesting depth — since a real tree is too deep to read as
    a single dense line; the same layout `touch -p` itself accepts back
    as input."""
    return render_signature(build_sig_data(node_path, with_transforms=True), FULL_SIGNATURE, pretty=True)


class LsCommand(Command):
    name = "ls"
    help = "list a node's own class, subnodes, and transforms, or (for a '/'-or-transform target) its directory content"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            nargs="?",
            default=".",
            help="Node.Path (class + subnodes + transforms) | Node.Path/rel/path or "
            "Node.Path.transformName (raw directory listing); defaults to the "
            "current node ('.'), which lists all top-level nodes if no "
            "current node is set",
        )
        parser.add_argument(
            "-r",
            action="store_true",
            help="recurse — show the full inclusion tree (or, for a '/'-or-"
            "transform target, the full directory tree) instead of just one level",
        )

    def run(self, args: argparse.Namespace) -> int:
        # An optional trailing "<NodeType arg1 arg2>" signature assertion
        # (e.g. "Foo.Bar<Chain>") may itself contain "(" (an unquoted
        # param value can, e.g. "x=(1)") — stripping the whole suffix
        # first keeps that from being mistaken for anything in the target
        # portion itself.
        stripped, type_name, expected_sig = _split_type_suffix(args.target)
        is_raw = is_raw_target(stripped)
        try:
            if is_raw:
                target_dir = resolve_target(args.target)
                names = list_dir_tree(target_dir) if args.r else list_dir(target_dir)
            else:
                node_path = expand(stripped)
                if type_name is not None and node_path != ROOT:
                    validate_node_signature(node_path, type_name, expected_sig, args.target)
                if args.r:
                    # "topology" has no real class of its own, so at the
                    # true root this is one full signature line per
                    # top-level node rather than one combined line under
                    # a synthetic root.
                    targets = list_root() if node_path == ROOT else [node_path]
                    tree_lines = [_render_node_tree(target) for target in targets]
                elif node_path != ROOT:
                    node_lines = _render_node(node_path)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if is_raw:
            for name in names:
                print(name)
            return 0

        if args.r:
            for line in tree_lines:
                print(line)
            return 0

        if node_path == ROOT:
            # "(@)<Topology>" -- a synthetic label for the true root,
            # which has no real class of its own -- with each top-level
            # node shown PascalCase, matching every other node name in
            # the grammar (its real snake_case directory name is what
            # `expand()`/`resolve_node_path` still take as input,
            # unaffected).
            names = ",".join(pascal_case(name) for name in list_root())
            print(f"({ROOT})<Topology>({names})")
            return 0

        for line in node_lines:
            print(line)
        return 0
