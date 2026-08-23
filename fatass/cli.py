import argparse
import sys

from ._import_tree import reload_all
from ._logging import get_logger
from .commands import ALL_COMMANDS


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(argv) if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(prog="fatass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ALL_COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help)
        command.add_arguments(sub)
        sub.set_defaults(_command=command)

    args = parser.parse_args(argv)
    exit_code = args._command.run(args)

    get_logger().info("%s -> exit %s", " ".join(effective_argv), exit_code)

    if args._command.mutates_topology:
        # Within one interpreter (notably the `shell` REPL) sys.modules
        # still holds whatever fatass.topology.* looked like before this
        # command ran — reload so a later command sees the current tree.
        reload_all("fatass.topology")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
