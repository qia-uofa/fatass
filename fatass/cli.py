import argparse
import sys

from ._internal.import_tree import reload_all
from ._internal.logs import get_logger
from .commands import ALL_COMMANDS, TOP_LEVEL_NAMES
from .commands._targets import _looks_like_transform_target
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


def _merge_paren_tokens(argv: list[str]) -> list[str]:
    """A raw command line's own whitespace tokenization (`shlex.split` in
    `shell.py`'s REPL, or the OS shell for a direct `python -m fatass ...`
    invocation) knows nothing about fatass's own "<...>"/"(...)" target/
    create-target grammar — a space after a comma inside parens (e.g.
    `build(a, b)@c`, `grid(ArrayTxt, dim=2x2x2)`), the space BETWEEN two
    entries of the space-separated "<NodeType name:type=value ...>" named-
    parameter form (e.g. `my_chat<Chat prompt:str=hi>`), or one embedded
    in a quoted value within either form (e.g. `Chat prompt:str="hello
    world"`), all get split into separate argv entries before fatass ever
    sees them. Re-join any run of consecutive tokens whose combined "("+
    "<" count outruns its combined ")"+">" count back into one token —
    with the whitespace between them restored as a single space (never
    dropped entirely, and shlex/the OS shell already collapse any run of
    whitespace down to a single split point before this ever runs, so one
    space is all there ever was to restore) — the same single token a
    fully-quoted version of the same text would already have produced.
    Correct either way a rejoined space lands: harmless where it merely
    duplicates an already-insignificant space (e.g. right after a comma,
    where downstream parsing already strips each entry), and essential
    where it's the only surviving trace of a meaningful space that was
    inside quotes moments earlier, at the shlex/shell layer, before that
    layer's own quote-stripping discarded the only signal marking it as
    protected — including the space-separated named-parameter form's own
    entry-separating spaces, which have no parens marking them as
    "still open" at all, only the outer "<...>": both bracket kinds are
    tracked together (one combined depth, not two separate ones) since
    by construction "<...>" is always the outer wrapper and "(...)"
    (when present at all) always nests inside it, never the reverse or
    interleaved, so they always reach zero at exactly the same token.
    A token (or already-merged run) that reaches balance (combined count
    zero, including the common case of no brackets at all) is left as
    its own token; genuinely unbalanced input (e.g. a stray "(" or "<" in
    freeform prompt text with no matching closer anywhere later on the
    line) degrades to merging everything after it into one token — quote
    such a prompt to avoid that, same as you'd need to for any other
    shell-special character."""
    merged: list[str] = []
    buffer = ""
    depth = 0
    for token in argv:
        buffer = token if depth <= 0 else buffer + " " + token
        depth += (
            token.count("(") - token.count(")") + token.count("<") - token.count(">")
        )
        if depth <= 0:
            merged.append(buffer)
            buffer = ""
            depth = 0
    if buffer:
        merged.append(buffer)
    return merged


def main(argv: list[str] | None = None) -> int:
    effective_argv = _merge_paren_tokens(
        list(argv) if argv is not None else sys.argv[1:]
    )
    parse_argv = effective_argv
    if parse_argv and parse_argv[0] in ALIASES:
        parse_argv = [ALIASES[parse_argv[0]], *parse_argv[1:]]
    elif (
        parse_argv
        and parse_argv[0] not in TOP_LEVEL_NAMES
        and _looks_like_transform_target(parse_argv[0])
    ):
        # Bare `Node.transform` (no leading command) is shorthand for
        # `apply Node.transform` — e.g. `MyNode.build key=value`.
        parse_argv = ["apply", *parse_argv]

    parser = argparse.ArgumentParser(prog="fatass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # A command with `group` set (e.g. "chain") nests one level down —
    # `fatass <group> <name>` instead of a bare `fatass <name>` — since
    # its primary argument must be a specific node kind, and grouping by
    # that kind reads more clearly than a flat list of every such command
    # mixed in with every unrestricted one. One shared sub-subparser
    # group per distinct `group` value, built lazily as each is first
    # encountered (`ALL_COMMANDS`' own order), rather than a fixed list —
    # a future node-kind-specific command just sets its own `group` and
    # falls into whichever bucket already exists, or starts a new one.
    group_subparsers: dict[str, argparse._SubParsersAction] = {}
    for command in ALL_COMMANDS:
        if command.group is None:
            sub = subparsers.add_parser(command.name, help=command.help)
        else:
            if command.group not in group_subparsers:
                group_parser = subparsers.add_parser(
                    command.group, help=f"{command.group}-specific commands"
                )
                group_subparsers[command.group] = group_parser.add_subparsers(
                    dest=f"{command.group}_command", required=True
                )
            sub = group_subparsers[command.group].add_parser(command.name, help=command.help)
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
        args._command.after_reload(args)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
