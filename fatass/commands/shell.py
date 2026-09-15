import argparse
import contextlib
import io
import shlex
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from .._internal.import_tree import reload_all
from .._internal.paths import OUT_ROOT, SHELL_HISTORY_PATH, SHELL_OUTPUT_PATH
from ..errors import TopologyValidationError
from ..resolve.cwd import (
    PAREN_ROOT,
    ROOT,
    display_current_node,
    enter_session,
    exit_session,
    expand,
    read_current_node,
    write_current_node,
)
from ..resolve.targets import resolve_file
from ..topology_ops.scaffold import _node_dir
from ._shell_completion import ShellCompleter
from .base import Command


def _protect_angle_spans(line: str) -> tuple[str, dict[str, str]]:
    """Replace each top-level "<...>" span in `line` (fatass's own node-
    type-suffix grammar — see `fatass.signature`) with a whitespace-free
    placeholder, before `shlex.split()` ever sees the line. `shlex` has
    no notion of this grammar — left alone, it would consume a
    `"..."`-quoted value inside the span (e.g. `Chat prompt:str="hello,
    world"`) for its OWN space-preservation purposes, permanently
    discarding the quote characters themselves before fatass's own
    parsing (`fatass.signature._tokenize_space_args`) ever gets a chance
    to see them and know that value's own internal spaces/commas need
    protecting — `cli._merge_paren_tokens` can restore a lost *space*
    (shlex only ever collapses one to a split point, nothing more to
    recover), but by the time it runs the quote *characters* are already
    gone for good, nothing left to restore them from.

    A `"..."`-quoted region inside the span is tracked while scanning
    (backslash-escaping honored, matching `_tokenize_space_args`'s own
    rules) so a stray "<"/">" inside a quoted value doesn't prematurely
    end the span. Returns the placeholder-substituted line and a mapping
    from each placeholder back to its original literal span text, for
    `_restore_angle_spans` to splice back in once `shlex.split()` (and
    `cli._merge_paren_tokens`, downstream) are done splitting/rejoining
    everything else."""
    spans: dict[str, str] = {}
    out: list[str] = []
    i, n = 0, len(line)
    counter = 0
    while i < n:
        if line[i] != "<":
            out.append(line[i])
            i += 1
            continue
        start = i
        depth = 1
        i += 1
        in_quotes = False
        while i < n and depth > 0:
            ch = line[i]
            if in_quotes:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == '"':
                    in_quotes = False
                i += 1
                continue
            if ch == '"':
                in_quotes = True
            elif ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            i += 1
        placeholder = f"\x00{counter}\x00"
        spans[placeholder] = line[start:i]
        out.append(placeholder)
        counter += 1
    return "".join(out), spans


def _restore_angle_spans(tokens: list[str], spans: dict[str, str]) -> list[str]:
    """Splice each placeholder `_protect_angle_spans` substituted back
    into whichever token it ended up in, restoring the original literal
    "<...>" span text (quotes and all) `shlex.split()` never actually
    saw."""
    if not spans:
        return tokens
    restored = []
    for token in tokens:
        for placeholder, original in spans.items():
            token = token.replace(placeholder, original)
        restored.append(token)
    return restored


def _split_redirect(line: str) -> tuple[str, str | None]:
    """Split a trailing, top-level (unquoted) ">> path" output-redirect
    off `line` — fatass shell's own redirect syntax (see
    `_resolve_redirect_path`) — returning `(command_line, path)`, or
    `(line, None)` if there's no such redirect. A ">>" inside a
    "..."-quoted value (e.g. a modify prompt that happens to mention it)
    is left alone, same quote-tracking convention as
    `_protect_angle_spans`/`touch._strip_comments`. Runs on the raw line
    BEFORE `_protect_angle_spans`/`shlex.split()` ever see it, so
    `command_line` alone is what gets parsed as the actual fatass
    command."""
    in_quotes = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if in_quotes:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            i += 1
            continue
        if ch == ">" and i + 1 < n and line[i + 1] == ">":
            return line[:i].rstrip(), line[i + 2 :].strip() or None
        i += 1
    return line, None


def _resolve_redirect_path(raw: str) -> Path:
    """Resolve `fatass shell`'s own ">> path" redirect target:

    - An absolute filesystem path is used as-is.
    - A "Node.Path/rel/file" target (the same "/" grammar `sh`/`vim`/
      `free` already use — see `fatass.resolve.targets.resolve_file`)
      writes under that node's own home/ assets directory — a bare
      "Node.Path/" with no filename after it is rejected (it resolves to
      a directory, not a file — give it one).
    - Anything else (no "/" — a bare relative filename) is written under
      `OUT_ROOT`, alongside the dispatch log and `fatass graph`'s own
      default output."""
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    if "/" in raw:
        resolved = resolve_file(raw)
        if resolved.is_dir():
            raise TopologyValidationError(
                f"{raw!r} resolves to a directory — include a filename "
                f"after the '/' to redirect output there"
            )
        return resolved
    return OUT_ROOT / raw


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
    """"@Tests.List2 >>> " (or "(@) >>> " at the root) — the current
    node, re-read fresh each time since a `cd` run through the loop
    below may have just changed it."""
    return f"{display_current_node()} >>> "


class ShellCommand(Command):
    name = "shell"
    help = "interactive REPL — type a fatass command per line"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "path",
            nargs="?",
            default=None,
            help="@node.path to cd to before entering the shell (must be "
            "absolute, i.e. start with '@' or '(@)'); omit to keep the "
            "current node",
        )

    def run(self, args: argparse.Namespace) -> int:
        # Deferred: cli.py imports commands/ at module load time (to build
        # ALL_COMMANDS), so `from ..cli import main` at module level here
        # would be a circular import. By the time run() executes, cli.py
        # has already finished loading.
        from ..cli import main

        if args.path is not None:
            if not (args.path.startswith(ROOT) or args.path.startswith(PAREN_ROOT)):
                print(
                    f"error: shell's path argument must be absolute (start with "
                    f"{ROOT!r} or {PAREN_ROOT!r}), got {args.path!r}",
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
        # cli.py -> commands (only needed here, for the completer's
        # command-name lists).
        from . import GROUP_SUBCOMMAND_NAMES, TOP_LEVEL_NAMES

        # A FileHistory (not InMemoryHistory) so `>>> ` lines persist to
        # .fatass/shell_history across every `fatass shell` invocation,
        # past and present — `fatass debug` reads its tail as one of its
        # two history sources (the other being out/log). session.prompt()
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
                completer=ShellCompleter(sorted(TOP_LEVEL_NAMES), GROUP_SUBCOMMAND_NAMES),
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

                last_error: str | None = None
                if line:
                    if use_plain_input:
                        # session.prompt() records accepted input into
                        # `history` on its own; bare input() doesn't, so
                        # the fallback path has to do it itself.
                        history.append_string(line)
                    command_line, redirect_raw = _split_redirect(line)
                    buffer = io.StringIO()
                    redirect_path: Path | None = None
                    try:
                        if redirect_raw is not None:
                            redirect_path = _resolve_redirect_path(redirect_raw)
                        protected_line, spans = _protect_angle_spans(command_line)
                        argv = _restore_angle_spans(shlex.split(protected_line), spans)
                        if redirect_path is not None:
                            # True redirect, not a tee — the whole point
                            # of ">>" is that this command's own output
                            # goes to the file INSTEAD of the console.
                            with contextlib.redirect_stdout(
                                buffer
                            ), contextlib.redirect_stderr(buffer):
                                main(argv)
                        else:
                            with contextlib.redirect_stdout(
                                _Tee(sys.stdout, buffer)
                            ), contextlib.redirect_stderr(_Tee(sys.stderr, buffer)):
                                main(argv)
                    except SystemExit:
                        pass  # argparse already printed its own error/help
                    except KeyboardInterrupt:
                        print()
                    except Exception as exc:
                        last_error = str(exc)
                        print(f"error: {exc}", file=sys.stderr)
                        buffer.write(f"error: {exc}\n")
                    if redirect_path is not None:
                        redirect_path.parent.mkdir(parents=True, exist_ok=True)
                        with redirect_path.open("a", encoding="utf-8") as fh:
                            fh.write(buffer.getvalue())
                        print(f"(output appended to {redirect_path})")
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
                    # `main()` above already reloads (and reports) for a
                    # mutates_topology command — don't print the exact same
                    # failure a second time when this catch-all pass hits it
                    # again on the still-broken tree.
                    if str(exc) != last_error:
                        print(f"error: {exc}", file=sys.stderr)
        finally:
            exit_session()

        return 0
