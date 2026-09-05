import argparse
import re
import sys
from pathlib import Path

from ..errors import TopologyValidationError
from ..resolve.targets import resolve_file
from ._targets import resolve_chain
from .base import Command

_WINDOWS_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def _is_real_fs_path(raw: str) -> bool:
    """True if `raw` looks like an absolute real filesystem path rather
    than a fatass target expression — a leading "/" (POSIX), a drive
    letter ("C:\\..."/"C:/..."), or a UNC path ("\\\\server\\share\\...").
    Unambiguous either way: a fatass node.path is dot-separated
    identifiers (never a drive letter or a leading slash — resolve()
    explicitly rejects a leading "/" as a likely shell-tilde-expansion
    accident), so nothing here could be mistaken for one."""
    return raw.startswith("/") or bool(_WINDOWS_ABS_RE.match(raw))


def _resolve_path_arg(raw: str) -> Path:
    """One of `insert`'s `path1 path2 ...` arguments: an absolute real
    filesystem path is used as-is (must exist); anything else is a
    fatass target expression (node.path / transform@node.path /
    node.path(rel/path)), resolved via resolve_file() to the actual file
    or directory it names."""
    if _is_real_fs_path(raw):
        path = Path(raw)
        if not path.exists():
            raise TopologyValidationError(f"{path} does not exist")
        return path
    return resolve_file(raw)


class InsertCommand(Command):
    name = "insert"
    help = "insert an item into a Chain at index n, shifting the rest back"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("n", type=int, help="index to insert at (0..len(node.path))")
        parser.add_argument("node_path", help="node.path of a Chain")
        parser.add_argument(
            "paths",
            nargs="*",
            help="files/dirs to seed the new item with (leaf lists only) — "
            "each either an absolute real filesystem path, or a fatass "
            "target expression (node.path / transform@node.path / "
            "node.path(rel/path)); omit to instead copy the dummy head's "
            "own current content",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            list_cls = resolve_chain(args.node_path)
            resolved_paths = [_resolve_path_arg(p) for p in args.paths] if args.paths else None
            list_cls.insert(args.n, paths=resolved_paths)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{list_cls._topology_path()}: inserted item {args.n}")
        return 0
