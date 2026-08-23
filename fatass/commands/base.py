import argparse
from abc import ABC, abstractmethod


class Command(ABC):
    """One `fatass <name>` subcommand."""

    name: str
    help: str

    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add this command's arguments to its argparse subparser."""

    @abstractmethod
    def run(self, args: argparse.Namespace) -> int:
        """Execute the command. Returns the process exit code."""
