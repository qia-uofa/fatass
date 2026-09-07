from pathlib import Path

from .._internal.paths import HOME_ROOT

_TOPOLOGY_PREFIX = "fatass.topology."
_NODE_PREFIX = "fatass.node."


class NodeMeta(type):
    """A `Node` subclass is almost always referred to as a class object
    itself (`Education.length()`, `Info.write(...)`), never instantiated
    (`Chain` is the one exception) — so a plain instance `__repr__` would
    never actually be seen. Overriding `__repr__` here, on the metaclass,
    is what makes `repr(SomeNodeClass)` itself show something useful
    (`fatass ls` and any debugging print of a node class) instead of
    Python's default `<class 'module.Name'>`.

    Shows the fatass framework kind the class is built on — its nearest
    `fatass.node.*`-defined ancestor in `__mro__` (most-specific first,
    so a typed variant like `SingleCsv`/`ArrayCsv` is picked over the
    plain `Single`/`Array` it's built on, and a bare `Node` subclass
    falls all the way back to `Node` itself) — plus that kind's own
    configuration: `DIM` (`Array`/its typed variants) and/or `FIELDS`
    (`Tuple`, `SingleCsv`, `ArrayCsv`), whichever the kind actually
    defines non-empty."""

    def __repr__(cls) -> str:
        kind = cls
        for base in cls.__mro__:
            if base.__module__.startswith(_NODE_PREFIX):
                kind = base
                break

        parts = []
        dim = getattr(cls, "DIM", ())
        if dim:
            parts.append("x".join(str(d) for d in dim))
        fields = getattr(cls, "FIELDS", ())
        if fields:
            parts.append(", ".join(fields))

        return f"{kind.__name__}({', '.join(parts)})"


class Node(metaclass=NodeMeta):
    """Base class for a node's definition.

    Subclassed once per `fatass/topology/.../<name>/<name>.py`. Carries no
    per-instance state — all path resolution is derived from where the
    subclass is defined (`cls.__module__`).
    """

    @classmethod
    def _topology_path(cls) -> str:
        module = cls.__module__
        if not module.startswith(_TOPOLOGY_PREFIX):
            raise ValueError(
                f"{cls!r} is not defined under fatass.topology "
                f"(module is {module!r})"
            )
        path = module[len(_TOPOLOGY_PREFIX):]
        # A Node subclass is defined inside its own <name>.py, so
        # cls.__module__ is always "...<name>.<name>" — one trailing segment
        # (the node's own file, always named after its own directory) more
        # than the node's actual topology path. Strip it unconditionally.
        return path.rsplit(".", 1)[0]

    @classmethod
    def _assets_dir(cls) -> Path:
        relative = cls._topology_path().replace(".", "/")
        return HOME_ROOT / relative

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        """Extra `--append-system-prompt` guidance for `fatass modify`
        when editing a node file that subclasses this class — appended
        after the static conventions/command prompts. None by default;
        override in a subclass (see Chain) to teach the agent
        conventions specific to that kind of node."""
        return None

    @classmethod
    def on_created(cls) -> None:
        """Called once, right after `fatass create` scaffolds a new node
        of this class and the topology tree is reloaded so the class is
        actually importable — a chance for a subclass with content of its
        own beyond a bare directory (see Single, Array) to materialize it
        immediately instead of waiting for first access. No-op by default:
        an ordinary Node has nothing to create beyond the empty home/
        directory `create_node()` already made."""
        return None

    @classmethod
    def purge_self(cls) -> int | None:
        """Override to replace `fatass purge`'s default behavior (delete
        every entry directly under this node's own home/ directory) with
        something else — e.g. clearing fixed-name file(s) in place instead
        of removing them (see Single, Array). Returns the number of
        entries purged, or None (the default) to mean "no override, use
        the generic delete-everything behavior"."""
        return None

    @classmethod
    def on_child_moved(cls, old_child_stem: str, new_child_stem: str) -> None:
        """Called on a node's own class, after `fatass move` renames one of
        its *direct* children in place (same parent, only the leaf segment
        changed) — a chance for a node class with its own extra structure
        mirroring its children's names (see `Chain`) to keep that mirror
        in sync. No-op by default: an ordinary `Node` has no such mirror,
        so `move_node`'s own generic topology/home/ directory move (already
        done by the time this is called) is the whole story. `move_node`
        calls this on the child's *parent's* class, unaware of what (if
        anything) that class actually needs to do about it."""
        return None
