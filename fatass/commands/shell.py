import argparse
import shlex
import sys

from .base import Command


class ShellCommand(Command):
    name = "shell"
    help = "interactive REPL — type a fatass command per line"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace) -> int:
        # Deferred: cli.py imports commands/ at module load time (to build
        # ALL_COMMANDS), so `from ..cli import main` at module level here
        # would be a circular import. By the time run() executes, cli.py
        # has already finished loading.
        from ..cli import main

        print("fatass shell — one command per line, e.g. `create foo`.")
        print("'exit'/'quit' or Ctrl-D to leave.")

        while True:
            try:
                line = input("fatass> ")
            except EOFError:
                print()
                break

            line = line.strip()
            if not line:
                continue
            if line in ("exit", "quit"):
                break

            try:
                main(shlex.split(line))
            except SystemExit:
                pass  # argparse already printed its own error/help
            except KeyboardInterrupt:
                print()
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)

        return 0
