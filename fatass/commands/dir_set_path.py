import argparse
import sys

from .._internal.naming import pascal_node_path
from ..core.transform import _resolve_owning_node
from ..errors import TopologyValidationError
from ..node.dir import Dir
from ..resolve.cwd import ROOT, expand
from ..signature import SIMPLE_TYPED, pathed_signature
from .base import Command


class DirSetPathCommand(Command):
    name = "set-path"
    group = "dir"
    help = "write a Dir's own '.path' file, giving it a real filesystem directory"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "node_path",
            help="node.path of a Dir — may be chain-indexed, e.g. 'Lectures[0].Assets'",
        )
        parser.add_argument("real_path", help="the real filesystem path to assign")

    def run(self, args: argparse.Namespace) -> int:
        try:
            node_path = expand(args.node_path)
            if node_path == ROOT:
                raise TopologyValidationError(
                    f"{args.node_path!r} resolved to the topology root, which isn't a node"
                )
            owning_cls, discovery_path, _cache_key_prefix = _resolve_owning_node(node_path)
            if not issubclass(owning_cls, Dir):
                raise TopologyValidationError(
                    f"{pathed_signature(discovery_path, SIMPLE_TYPED, max_depth=0)} is not a Dir"
                )
            target_dir = owning_cls._home_fallback_dir()
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / ".path").write_text(args.real_path, encoding="utf-8")
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{pascal_node_path(node_path)}: path set to {args.real_path}")
        return 0
