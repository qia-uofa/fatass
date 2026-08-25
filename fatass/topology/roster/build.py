import fatass
from fatass.topology.roster import Roster as Roster


def build():
    """No Node-typed parameter: this reads across `Roster`'s own items,
    not a statically importable dependency — an index isn't known until
    run time, so there's nothing to declare here the way a normal
    dependency would be. See `entry`'s own `build` for the per-item half
    of this pipeline."""
    entries = [Roster()[i].entry for i in range(Roster.length())]

    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=entries,
        prompt=(
            "Each dependency's readable directory holds one roster "
            "entry, written by `roster.entry`'s own `build` transform "
            "(`entry.md`: an invented person's name, role, and a fun "
            "fact). Read all of them and write `summary.md` in the "
            "current directory: one bullet per entry, in the order "
            "given, plus a one-line total count at the top."
        ),
    )
