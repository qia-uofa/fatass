import argparse
from abc import ABC, abstractmethod


class Command(ABC):
    """One `fatass <name>` subcommand."""

    name: str
    help: str
    mutates_topology: bool = False
    """True for a command that changes fatass/topology/ itself (creating,
    editing, moving, removing, archiving, or retrieving node/transform
    files) — cli.main() reloads the already-imported fatass.topology tree
    after such a command runs, so a later command in the same process
    (e.g. inside the `shell` REPL) doesn't see stale module state."""

    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add this command's arguments to its argparse subparser."""

    @abstractmethod
    def run(self, args: argparse.Namespace) -> int:
        """Execute the command. Returns the process exit code."""
