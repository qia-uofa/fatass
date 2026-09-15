import argparse
import sys

from ..core.transform import _resolve_owning_node
from ..errors import TopologyValidationError
from ..node.dir import Dir
from ..resolve.cwd import ROOT, expand
from ..signature import SIMPLE_TYPED, pathed_signature
from .base import Command


class DirPathCommand(Command):
    name = "path"
    group = "dir"
    help = "print a Dir node's resolved real filesystem path"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "node_path",
            help="node.path of a Dir — may be chain-indexed, e.g. "
            "'Lectures[0].Assets'",
        )

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
            resolved = owning_cls._assets_dir()
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(resolved)
        return 0
