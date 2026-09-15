import argparse
from abc import ABC, abstractmethod


class Command(ABC):
    """One `fatass <name>` subcommand — or, if `group` is set, one
    `fatass <group> <name>` subcommand nested under that node-type
    group."""

    name: str
    help: str
    group: str | None = None
    """Lowercase name of the specific node kind this command's primary
    argument must be (e.g. "chain" for a command that only makes sense
    against a `Chain`) — `None` (the default) for a command with no such
    restriction, registered directly at the top level. A non-`None`
    value nests this command one level down: `fatass <group> <name>`
    instead of a bare `fatass <name>` — see `cli.main()`."""
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

    def after_reload(self, args: argparse.Namespace) -> None:
        """Called by cli.main() right after fatass.topology is reloaded
        post-command (only for a mutates_topology command) — a chance to
        do something that needs the just-changed topology tree actually
        importable, which wasn't true yet during run() itself (e.g.
        CreateCommand calling a freshly-scaffolded node class's own
        on_created()). No-op by default."""
        return None
