import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from ..errors import TopologyValidationError
from ..resolve.targets import resolve_file
from .base import Command


def _find_vim() -> str | None:
    """`vim` itself, if directly on PATH. On Windows, Git for Windows
    bundles its own vim.exe (the one Git Bash uses) under
    <git install root>/usr/bin/vim.exe, but that directory usually isn't
    on PATH outside of a Git Bash session — fall back to deriving it from
    wherever `git` itself is (already on PATH for anyone using this repo)
    instead of requiring a second, separate PATH edit on top of Git's own
    installer."""
    found = shutil.which("vim")
    if found:
        return found
    if platform.system() != "Windows":
        return None
    git = shutil.which("git")
    if not git:
        return None
    candidate = Path(git).parent.parent / "usr" / "bin" / "vim.exe"
    return str(candidate) if candidate.is_file() else None


class VimCommand(Command):
    name = "vim"
    help = "open a node's class file, a transform file, or a home/ file in vim"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help="node.path (class file) | transform@node.path (transform file) | "
            "node.path(relative/file/path) (home/ file)",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            file_path = resolve_file(args.target)
        except TopologyValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        vim_exe = _find_vim()
        if vim_exe is None:
            print("error: `vim` was not found on PATH", file=sys.stderr)
            return 1

        try:
            result = subprocess.run([vim_exe, str(file_path)])
        except FileNotFoundError:
            print("error: `vim` was not found on PATH", file=sys.stderr)
            return 1
        return result.returncode
