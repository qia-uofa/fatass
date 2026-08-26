import argparse
import sys

from ..errors import TopologyValidationError
from ..topology_ops.bind import bind_transform, bound_dep_paths, unbind_transform
from ._targets import parse_at_target, resolve_node_path
from .base import Command


class BindCommand(Command):
    name = "bind"
    help = "add one or more nodes as declared Node-typed dependencies on a transform"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="<transform>@<node.path>")
        parser.add_argument(
            "deps",
            nargs="*",
            help="one or more node.path arguments to bind as inputs; required "
            "unless -a/--absolute is given",
        )
        parser.add_argument(
            "-a",
            "--absolute",
            action="store_true",
            help="replace the transform's entire dependency set with exactly "
            "these deps (unbinds every currently bound dep first) instead of "
            "adding to it; with no deps at all, just clears every existing bind",
        )

    def run(self, args: argparse.Namespace) -> int:
        if not args.absolute and not args.deps:
            print("error: at least one dep.path is required (or pass -a/--absolute)", file=sys.stderr)
            return 1

        try:
            node_path, transform_name = parse_at_target(args.target)
            dep_paths = [resolve_node_path(d) for d in args.deps]

            if args.absolute:
                removed = bound_dep_paths(node_path, transform_name)
                if removed:
                    unbind_transform(node_path, transform_name, removed)
                bound = bind_transform(node_path, transform_name, dep_paths) if dep_paths else []
            else:
                removed = []
                bound = bind_transform(node_path, transform_name, dep_paths)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        label = f"{transform_name}@{node_path}"
        if removed:
            print(f"{label}: unbound {', '.join(removed)}")
        if bound:
            print(f"{label}: bound {', '.join(bound)}")
        skipped = [d for d in dep_paths if d not in bound]
        if skipped:
            print(f"{label}: already bound {', '.join(skipped)}")
        if not removed and not bound and not skipped:
            print(f"{label}: no dependencies")
        return 0
