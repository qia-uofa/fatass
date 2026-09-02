import argparse
import sys

from ._internal.import_tree import reload_all
from ._internal.logs import get_logger
from .commands import ALL_COMMANDS
from .resolve.cwd import display_current_node

# Alternate spellings for existing commands (e.g. familiar Unix names) —
# purely cosmetic, resolved to the real command name before argparse ever
# sees it, so help/completion/logging all still show one canonical name.
ALIASES = {
    "mkdir": "create",
    "mv": "move",
    "cp": "copy",
    "rm": "remove",
}


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    parse_argv = effective_argv
    if parse_argv and parse_argv[0] in ALIASES:
        parse_argv = [ALIASES[parse_argv[0]], *parse_argv[1:]]
    elif (
        parse_argv
        and "@" in parse_argv[0]
        and parse_argv[0] not in {c.name for c in ALL_COMMANDS}
    ):
        # Bare `<transform>@<node>` (no leading command) is shorthand for
        # `apply <transform>@<node>` — e.g. `build@my.node key=value`.
        parse_argv = ["apply", *parse_argv]

    parser = argparse.ArgumentParser(prog="fatass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ALL_COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help)
        command.add_arguments(sub)
        sub.set_defaults(_command=command)

    args = parser.parse_args(parse_argv)
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
