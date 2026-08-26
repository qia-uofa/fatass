import argparse
import sys

from ._internal.import_tree import reload_all
from ._internal.logs import get_logger
from .commands import ALL_COMMANDS
from .resolve.cwd import display_current_node


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(argv) if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(prog="fatass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ALL_COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help)
        command.add_arguments(sub)
        sub.set_defaults(_command=command)

    args = parser.parse_args(argv)
    # Read before dispatch, so a `cd` command's own line still logs the
    # node it ran *from* — matching what the `shell` prompt showed the
    # user right before they typed it, not the node it just changed to.
    current = display_current_node()
    exit_code = args._command.run(args)

    get_logger().info("%s %s -> exit %s", current, " ".join(effective_argv), exit_code)

    if args._command.mutates_topology:
        # Within one interpreter (notably the `shell` REPL) sys.modules
        # still holds whatever fatass.topology.* looked like before this
        # command ran — reload so a later command sees the current tree.
        reload_all("fatass.topology")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
