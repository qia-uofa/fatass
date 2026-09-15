import argparse

from .._internal.naming import pascal_node_path
from ..resolve.cwd import PAREN_ROOT, ROOT, read_current_node
from .base import Command


class PwdCommand(Command):
    name = "pwd"
    help = "print the current node (FATASS_NODE)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace) -> int:
        current = read_current_node()
        print(PAREN_ROOT if current == ROOT else pascal_node_path(current))
        return 0
