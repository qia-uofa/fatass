from pathlib import Path

from .._internal.naming import escape_snake_case
from ..errors import TopologyValidationError
from .node import Node, NodeMeta

_SYS_PROMPT = """## `Dir` — a node backed by a real filesystem directory, not `home/`

This node's own content lives at a real filesystem path (`PATH`), not
under fatass's own `home/` tree — `_assets_dir()` resolves there directly.
A root `Dir` (absolute `PATH`) mirrors an *existing* directory: every one
of its real subdirectories was scaffolded as its own nested `Dir`
subnode (relative `PATH` = that subdirectory's own name) when this node
was created. A non-root `Dir` (relative `PATH`) instead names a
directory to create fresh, resolved by chaining relative segments up
through its `Dir` ancestors to the nearest root.

`PATH` is never a class attribute you write yourself — it's a property
(see `DirMeta`) that reads a plain text file, `.path`, written into a
`home/` location (`fatass create`'s own `<Dir somewhere>` argument, `fatass
dir set-path`, or by hand) instead — same "write it yourself" idiom as
any other per-item content in a `Chain`. Two tiers, checked in order:

1. This index's own override — `_index_home_dir()/.path` — only if `cls`
   was reached via chain indexing (e.g. `some_chain[i].a_dir_child`).
2. The schema-level default — `home/<topology.path>/.path`, the node's
   own ordinary, index-independent `home/` location — shared by every
   index of a chain-indexed `Dir` (the same topological invariant that
   makes `A[i].B` and `A[j].B` share one schema applies here too), and
   the only tier a non-indexed `Dir` ever has.

An empty `PATH` (neither tier has a `.path` file, or the one that's
checked is empty) isn't an error — it just means no real directory is
assigned for now, and this node behaves like a plain `Node` (ordinary
`home/` location) until one is."""


class DirMeta(NodeMeta):
    """Makes `SomeDir.PATH` a computed property instead of a plain class
    attribute — see `Dir`'s own docstring for why. A `property` defined
    directly on `Dir` would only intercept *instance* attribute access
    (`SomeDir().PATH`), never `SomeDir.PATH` itself, since every node
    everywhere is referred to as a class object, never instantiated
    (`NodeMeta.__repr__`'s own docstring). A data descriptor on the
    metaclass is what makes class-level access go through it instead —
    and, since a data descriptor always wins over anything in the
    class's own `__dict__`/MRO, a `Dir` subclass can no longer shadow it
    with a plain `PATH = "..."` line (which is exactly the point: there
    is no other source of truth for `PATH` left to shadow it with)."""

    @property
    def PATH(cls) -> str:
        for candidate in (cls._path_override_file(), cls._schema_path_file()):
            if candidate is not None and candidate.is_file():
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    return content
        return ""


class Dir(Node, metaclass=DirMeta):
    """A `Node` whose `_assets_dir()` is a real filesystem directory
    instead of the usual `home/<topology.path>` location.

    - `PATH` absolute → this is a *root* `Dir` (`is_root()` True):
      mirrors an existing directory, or starts a fresh one if `PATH`
      doesn't exist yet (`on_created()` creates it). Either way,
      `on_created()` then scans it and scaffolds one `Dir` subnode per
      direct subdirectory, recursively — each subnode's own `PATH` is
      just that subdirectory's name, relative to *its* parent — so the
      topology ends up mirroring the real directory tree underneath
      this node (trivially empty for a freshly-created one).
    - `PATH` relative → this node must be nested (directly or through
      further relative-`PATH` `Dir` nodes) under a root `Dir`.
      `_resolved_path()` walks up through parent `Dir` nodes, joining
      relative segments, until it reaches a root's own absolute path.
      `on_created()` creates that resolved directory if it doesn't
      already exist (unlike a root, a relative `Dir` may be brand new —
      nothing to mirror).
    - `PATH` empty (no `.path` file yet — see `_path_override_file()`)
      → not a real directory at all yet; behaves like a plain `Node`
      instead, resolving to the ordinary `home/` location (per-index, if
      reached via chain indexing) rather than raising. The unconfigured
      default, and a legitimate steady state for an index that simply
      doesn't have (or doesn't yet need) a real directory assigned.
    """

    @classmethod
    def _path_override_file(cls) -> Path | None:
        """This index's own override of `PATH` (see `DirMeta.PATH`,
        tier 1) — inside `_index_home_dir()`, the home/-tree bookkeeping
        slot `NodeMeta.__getattr__`/`_ChainItem.__getattr__` stamp on a
        class derived via chain indexing (e.g. `some_chain[i]
        .a_dir_child`) — `None` for an ordinary, non-indexed `Dir`
        (which has only the schema-level tier, `_schema_path_file()`,
        below — there's no separate per-index slot to override with).
        Written by hand, plain file I/O, or via `fatass dir set-path` —
        same "write it yourself" idiom as a `Chain` item's own `.entry`
        file — not managed by fatass itself."""
        index_home_dir = getattr(cls, "_index_home_dir", None)
        if index_home_dir is None:
            return None
        return index_home_dir() / ".path"

    @classmethod
    def _schema_path_file(cls) -> Path:
        """The schema-level default `.path` file (see `DirMeta.PATH`,
        tier 2) — always at this node's own plain, index-independent
        `home/<topology.path>` location (`Node._assets_dir()`, the
        SAME real directory for every index of a chain-indexed `Dir` by
        the topological invariant — never `_index_home_dir()`, which
        would make it just another per-index override instead of a
        shared default). What `fatass create <path><Dir somewhere>`
        itself writes at creation time (see `scaffold.create_node`)."""
        return Node._assets_dir.__func__(cls) / ".path"

    @classmethod
    def is_root(cls) -> bool:
        return Path(cls.PATH).is_absolute()

    @classmethod
    def _parent_node_path(cls) -> str | None:
        path = cls._topology_path()
        return path.rsplit(".", 1)[0] if "." in path else None

    @classmethod
    def _resolved_path(cls) -> Path:
        """The real filesystem directory this node represents: `PATH`
        itself for a root `Dir`; otherwise `PATH` joined onto the
        nearest ancestor root `Dir`'s own resolved path, chained through
        every relative-`PATH` `Dir` in between.

        When reached as a schema child of an indexed `Chain` item (e.g.
        `some_chain[i].a_dir_child`), `_parent_indexed` (stamped by
        `NodeMeta.__getattr__`/`_ChainItem.__getattr__`) is the actual
        parent object *at that index* — not just this node's bare,
        index-independent schema class — so a relative path chains
        through the real indexed lineage instead of every index
        collapsing onto the same unindexed parent's resolved path."""
        if cls.is_root():
            return Path(cls.PATH)

        if not cls.PATH:
            # Empty, not merely relative — this node itself has no real
            # PATH assigned yet at all (see the class docstring's own
            # empty-PATH bullet), a distinct condition from "PATH is a
            # real relative segment but needs a Dir ancestor to resolve
            # against" below: whether or not a Dir ancestor exists, there
            # is no path segment of this node's own to join onto it.
            raise TopologyValidationError(
                f"{cls._topology_path()}: no PATH assigned yet (empty) — "
                f"write its '.path' file (see `Dir.PATH`'s own docstring — "
                f"by hand, or via `fatass dir set-path`) before it, or "
                f"anything nested under it, can resolve to a real directory"
            )

        parent = getattr(cls, "_parent_indexed", None)
        if parent is None:
            parent_path = cls._parent_node_path()
            if parent_path is None:
                raise TopologyValidationError(
                    f"{cls._topology_path()}: a relative Dir PATH ({cls.PATH!r}) "
                    f"must be nested under a root Dir (absolute PATH) node — "
                    f"this one has no parent node at all"
                )

            from ..core.transform import _import_node  # local: avoid a cycle

            parent = _import_node(parent_path)

        if not hasattr(parent, "_resolved_path"):
            parent_label = parent.__name__ if isinstance(parent, type) else type(parent).__name__
            raise TopologyValidationError(
                f"{cls._topology_path()}: a relative Dir PATH requires its "
                f"parent node to also be a Dir, got {parent_label}"
            )
        return parent._resolved_path() / cls.PATH

    @classmethod
    def _home_fallback_dir(cls) -> Path:
        """Where this `Dir` resolves when `PATH` is empty — also where
        its `.path` override file itself lives (see
        `_path_override_file()`) — `_index_home_dir()`, this index's own
        `home/`-tree bookkeeping slot, if `cls` was reached via chain
        indexing (so it stays distinct per index, exactly like an
        ordinary schema child would); otherwise the plain `Node` default
        (`home/<topology.path>`)."""
        index_home_dir = getattr(cls, "_index_home_dir", None)
        if index_home_dir is not None:
            return index_home_dir()
        return Node._assets_dir.__func__(cls)

    @classmethod
    def _assets_dir(cls) -> Path:
        if not cls.PATH:
            return cls._home_fallback_dir()
        return cls._resolved_path()

    @classmethod
    def _mirror_subdirs(cls, real_dir: Path) -> None:
        """One `Dir` subnode per direct subdirectory of `real_dir`,
        recursively — each scaffolded with its own relative `PATH` (the
        real subdirectory's own name, exact case and all — that's what
        actually has to match on disk for `_resolved_path()` to find it
        again) and immediately mirrored in turn, so one call at the root
        walks the whole existing tree in one pass. The node's own path
        segment (its class/file/home-dir name) is a separate thing from
        `PATH` and follows the same snake_case convention every other
        node path does — `escape_snake_case()`'d from the real name
        (never used verbatim), so a real directory can be named
        *anything* (`"MyCoolFolder"`, `"my-notes"`, `"2024 reports"`,
        `"_private"`, ...) and still become a valid, collision-free node
        name (`my_cool_folder`, `my_escdash_notes`, `esc2024_reports`,
        `escuds1_private`) instead of either breaking the PascalCase-
        input convention every other command's `cwd.expand` enforces
        (a node whose own path segment is itself capitalized/camelCased)
        or being skipped outright. A dotfile-style directory (e.g.
        `.git`) is still skipped deliberately — real, meaningful
        subdirectories essentially never start with "." — rather than
        mirrored as a node just because `escape_snake_case` *could* turn
        it into one."""
        from ..core.transform import _import_node  # local: avoid a cycle
        from ..topology_ops.scaffold import create_node  # local: avoid a cycle

        own_path = cls._topology_path()
        for entry in sorted(real_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            child_stem = escape_snake_case(entry.name)
            child_path = f"{own_path}.{child_stem}"
            create_node(child_path, base_class="Dir", class_kwargs={"path": entry.name})
            child_cls = _import_node(child_path)
            child_cls._mirror_subdirs(entry)

    @classmethod
    def on_created(cls) -> None:
        if not cls.PATH:
            # No real directory named at all — behaves like a plain
            # `Node`, whose own `on_created()` is a no-op (the `home/`
            # fallback dir `_assets_dir()` resolves to is created lazily
            # on access, same as any ordinary node's).
            return
        if cls.is_root():
            resolved = cls._resolved_path()
            if not resolved.is_dir():
                print(f"{cls._topology_path()}: root Dir path {resolved} does not exist, creating it")
                resolved.mkdir(parents=True)
            print(f"{cls._topology_path()}: mirroring subdirectories of {resolved}")
            cls._mirror_subdirs(resolved)
            return
        try:
            resolved = cls._resolved_path()
        except TopologyValidationError:
            # This Dir's OWN path is a real, non-empty relative segment
            # (e.g. "Assets") — the problem is further up the chain: some
            # ancestor Dir isn't configured with a real PATH yet (still
            # empty, "not yet pointed at anything" — see `Node._type_args`
            # /the `Dir` class docstring's own empty-PATH bullet). That's
            # a legitimate, expected state for a node structure declared
            # ahead of knowing the real path (e.g. scaffolded via `fatass
            # touch` from a template) — defer creating this directory
            # until the ancestor is configured and something re-resolves
            # it (`fatass dir mirror`, or simply accessing `_assets_dir()`
            # again later), rather than failing the whole scaffolding
            # operation over what only amounts to "not configured yet".
            return
        resolved.mkdir(parents=True, exist_ok=True)

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return _SYS_PROMPT
