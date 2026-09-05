import argparse
import contextlib
import io
import shlex
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from .._internal.import_tree import reload_all
from .._internal.paths import SHELL_HISTORY_PATH, SHELL_OUTPUT_PATH
from ..errors import TopologyValidationError
from ..resolve.cwd import (
    ROOT,
    display_current_node,
    enter_session,
    exit_session,
    expand,
    read_current_node,
    write_current_node,
)
from ..topology_ops.scaffold import _node_dir
from ._shell_completion import ShellCompleter
from .base import Command


class _Tee(io.TextIOBase):
    """Writes to every stream in `streams` — used to mirror the shell's
    own console output into an in-memory buffer (for persisting to
    SHELL_OUTPUT_PATH) while still printing live to the real console."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, s: str) -> int:
        for stream in self._streams:
            stream.write(s)
        return len(s)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _append_output_history(line: str, output: str) -> None:
    """Append one command's `>>> ` line and whatever it printed to
    SHELL_OUTPUT_PATH — read back by `fatass debug` (see
    topology_ops.scaffold._shell_output_excerpt) alongside the plain
    command-line history, so debugging context includes actual command
    output (errors, results), not just what was typed."""
    SHELL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SHELL_OUTPUT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f">>> {line}\n{output}\n")


def _prompt() -> str:
    """"~.tests.list2 >>> " (or just "~ >>> " at the root) — the current
    node, re-read fresh each time since a `cd` run through the loop below
    may have just changed it."""
    return f"{display_current_node()} >>> "


class ShellCommand(Command):
    name = "shell"
    help = "interactive REPL — type a fatass command per line"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "path",
            nargs="?",
            default=None,
            help="~.node.path to cd to before entering the shell (must be "
            "absolute, i.e. start with '~'); omit to keep the current node",
        )

    def run(self, args: argparse.Namespace) -> int:
        # Deferred: cli.py imports commands/ at module load time (to build
        # ALL_COMMANDS), so `from ..cli import main` at module level here
        # would be a circular import. By the time run() executes, cli.py
        # has already finished loading.
        from ..cli import main

        if args.path is not None:
            if not args.path.startswith(ROOT):
                print(
                    f"error: shell's path argument must be absolute (start with {ROOT!r}), "
                    f"got {args.path!r}",
                    file=sys.stderr,
                )
                return 1
            try:
                node_path = expand(args.path)
                if node_path != ROOT and not _node_dir(node_path).is_dir():
                    raise TopologyValidationError(f"no node at {node_path!r}")
            except TopologyValidationError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            write_current_node(node_path)

        # From here on, `cd`/`pwd` (and anything else resolving a target)
        # use this session's own in-memory current node instead of the
        # shared .fatass/.env file — so a `cd` in this shell doesn't leak
        # into a concurrent `fatass shell` session or any other process.
        # Seeded from whatever the current node already was (just set
        # above if --path was given, else whatever the dotenv file had).
        enter_session(read_current_node())

        print("fatass shell — one command per line, e.g. `create foo`.")
        print("'exit'/'quit' or Ctrl-D to leave.")
        print("Up/Down for history, Tab to complete commands and node paths.")

        # Local import: avoid a commands/-package-load-time cycle through
        # cli.py -> commands (ALL_COMMANDS is only needed here, for the
        # completer's command-name list).
        from . import ALL_COMMANDS

        # A FileHistory (not InMemoryHistory) so `>>> ` lines persist to
        # .fatass/shell_history across every `fatass shell` invocation,
        # past and present — `fatass debug` reads its tail as one of its
        # two history sources (the other being ./log). session.prompt()
        # appends to it automatically on each accepted line; the plain-
        # input fallback below appends manually, since bypassing
        # session.prompt() also bypasses that.
        SHELL_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(SHELL_HISTORY_PATH))

        # prompt_toolkit needs a real console (it queries the Windows
        # console API directly on this platform) — unavailable under some
        # terminals/test harnesses (e.g. mintty/Git Bash), where either
        # constructing the session or its first prompt() raises instead of
        # reading a line. Fall back to plain `input()` (no history/
        # completion, but still usable) whenever that happens, rather than
        # crashing the whole session.
        session: PromptSession | None
        try:
            session = PromptSession(
                history=history,
                completer=ShellCompleter([c.name for c in ALL_COMMANDS]),
            )
            use_plain_input = False
        except Exception:
            session = None
            use_plain_input = True

        try:
            while True:
                try:
                    line = (
                        input(_prompt())
                        if use_plain_input
                        else session.prompt(_prompt())  # type: ignore[union-attr]
                    )
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print()
                    continue
                except Exception:
                    use_plain_input = True
                    try:
                        line = input(_prompt())
                    except EOFError:
                        print()
                        break

                line = line.strip()
                if line in ("exit", "quit"):
                    break

                if line:
                    if use_plain_input:
                        # session.prompt() records accepted input into
                        # `history` on its own; bare input() doesn't, so
                        # the fallback path has to do it itself.
                        history.append_string(line)
                    buffer = io.StringIO()
                    try:
                        with contextlib.redirect_stdout(
                            _Tee(sys.stdout, buffer)
                        ), contextlib.redirect_stderr(_Tee(sys.stderr, buffer)):
                            main(shlex.split(line))
                    except SystemExit:
                        pass  # argparse already printed its own error/help
                    except KeyboardInterrupt:
                        print()
                    except Exception as exc:
                        print(f"error: {exc}", file=sys.stderr)
                        buffer.write(f"error: {exc}\n")
                    _append_output_history(line, buffer.getvalue())

                # Reload after every iteration — even a blank line — not
                # just a mutating command (cli.main()'s own reload is
                # conditional on Command.mutates_topology). Anything on
                # disk may have changed between prompts — a hand-edit in
                # another editor, a `vim` session — so the shell stays
                # current with no need to restart it; wrapped so a
                # currently-broken file (mid-edit) reports an error
                # instead of killing the session.
                try:
                    reload_all("fatass.topology")
                except Exception as exc:
                    print(f"error: {exc}", file=sys.stderr)
        finally:
            exit_session()

        return 0
