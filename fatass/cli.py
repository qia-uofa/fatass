import argparse
import sys

from .commands import ALL_COMMANDS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fatass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ALL_COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help)
        command.add_arguments(sub)
        sub.set_defaults(_command=command)

    args = parser.parse_args(argv)
    return args._command.run(args)


if __name__ == "__main__":
    sys.exit(main())
