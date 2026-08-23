import argparse

from ..cwd import read_current_node
from .base import Command


class PwdCommand(Command):
    name = "pwd"
    help = "print the current node (FATASS_NODE)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace) -> int:
        print(read_current_node())
        return 0
