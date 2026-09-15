import re
import shutil
from pathlib import Path

from .._internal.fs import copy_dir_contents
from ..errors import TopologyValidationError
from .node import Node

_ITEMS = ".items"
_ENTRY = ".entry"

_ILLEGAL_KEY_CHARS = re.compile(r'[\\/.\[\],:*?"<>|\x00-\x1f]')
_RESERVED_KEYS = {_ENTRY, _ITEMS, ".", ".."}


def _validate_key(dict_path: str, key: str) -> None:
    """A `Dictionary` key becomes a real directory name, LITERALLY (no
    escaping) — so it has to already be a safe one. Disallows path
    separators and other filesystem-illegal characters, the two reserved
    names (`_ENTRY`/`_ITEMS`) a key could otherwise collide with, and
    "."/","/"["/"]" — not filesystem-illegal, but each one is structurally
    significant in the `Dictionary[key]` bracket-target grammar (the
    topology-path separator, the multi-index separator, the bracket
    delimiters themselves) and would make a key ambiguous to address
    even with quoting. Leading/trailing whitespace and a trailing "."
    are also rejected (Windows silently strips both from a real
    directory name, so a key that differs from its own real directory
    name on disk would never round-trip)."""
    if not key:
        raise TopologyValidationError(f"{dict_path}: a Dictionary key can't be empty")
    if key in _RESERVED_KEYS:
        raise TopologyValidationError(
            f"{dict_path}: {key!r} is a reserved name, can't be used as a Dictionary key"
        )
    if _ILLEGAL_KEY_CHARS.search(key):
        raise TopologyValidationError(
            f"{dict_path}: {key!r} isn't a valid Dictionary key — it becomes a "
            f'real directory name (and is addressed via "Dictionary[key]"), so '
            f'\\ / . [ ] , : * ? " < > | and control characters are not allowed'
        )
    if key != key.strip() or key.endswith("."):
        raise TopologyValidationError(
            f"{dict_path}: {key!r} isn't a valid Dictionary key — can't start "
            f"or end with whitespace, or end with '.'"
        )


_SYS_PROMPT = """## `Dictionary` — a keyed collection of nodes, addressed by name instead of position

This node is (or should become) `class Node(fatass.Dictionary): pass` — a
collection of items addressed by an arbitrary string key rather than a
sequential position (see `Chain` for the positional equivalent). The
actual items live entirely inside this node's own `home/` directory,
never as new topology nodes:

```
members/
  info/            ← dummy head: schema mirror, content always ignored (only if schema children are declared — see "structured dicts" below)
  .entry/          ← dummy head's own default content — reserved name, exists only for parity with a real item
  .items/           ← reserved name, holds every real keyed entry
    alice/          ← members["alice"]
      info/
      .entry/
    bob/            ← members["bob"]
      info/
      .entry/
```

- `.set(key)` and `.keys()`/`.length()` are classmethods, called
  directly on the dictionary class itself (`Members.set("alice")`,
  `Members.keys()`). `.set(key)` is idempotent — it creates `key`'s own
  entry if it doesn't already exist yet, and is a harmless no-op
  (returning the existing directory) if it does; unlike `Chain.extend()`,
  there's no "always append a new one" concept for a keyed collection.
- Indexing (`members["alice"]`) needs an *instance*
  (`members = Members()`), not the class — `__getitem__` is an instance
  method, separate from the classmethods above. It raises if `"alice"`
  hasn't been `.set()` yet.
- **Leaf dicts — the common case, one thing per key, no further
  structure:** don't declare any schema children at all. Just index and
  write: `members["alice"]._assets_dir()` resolves straight to a
  reserved `.entry` directory under that key, creating it lazily on
  first access.
- **Structured dicts — each item needs more than one named field:**
  declare the per-item schema as the dictionary's own ordinary child
  nodes, same as any node's children. `members["alice"].info` then
  resolves to that key's own version of the schema child, creating its
  directory on first access — same lazy-creation, write-it-yourself
  pattern as `.entry` above.
- A key is a real directory name (no escaping) — see `.set()`'s own
  validation for exactly which characters are disallowed and why (a
  handful of filesystem-illegal characters, plus "." / "," / "[" / "]",
  which are structurally significant in the `Dictionary[key]`
  bracket-target grammar itself).
- `fatass dict keys`/`set`/`pop` (CLI, no agent call) manage entries
  directly: `dict keys <node.path>` lists every current key; `dict set
  <node.path> <key>` creates one if missing; `dict pop <node.path> <key>`
  removes it outright — unlike `Chain.pop`, nothing else shifts, since
  keys have no position to shift into."""


class Dictionary(Node):
    """A `Node` whose actual content is a keyed collection living
    entirely inside its own `home/` directory — no new topology node is
    ever created per key. See `Chain` for the positional equivalent this
    mirrors; the two differ in exactly the ways a flat, name-keyed
    collection differs from an ordered, position-keyed one — no
    insert/pop-with-shift machinery here, since removing one key never
    changes any other key's own identity."""

    @classmethod
    def _items_dir(cls) -> Path:
        target_dir = cls._assets_dir() / _ITEMS
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @classmethod
    def _entry_dir(cls) -> Path:
        """The dummy head's own `.entry` — same reserved name, and same
        "structurally identical to a real item, just ignored by
        convention" role, as `Chain._entry_dir()`."""
        target_dir = cls._assets_dir() / _ENTRY
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @classmethod
    def _has_schema_children(cls) -> bool:
        # Local import: same load-order reasoning as Chain's own.
        from ..topology_ops.scaffold import _all_node_paths

        own_path = cls._topology_path()
        prefix = f"{own_path}."
        return any(
            p.startswith(prefix) and "." not in p[len(prefix) :] for p in _all_node_paths()
        )

    @classmethod
    def keys(cls) -> list[str]:
        items_dir = cls._assets_dir() / _ITEMS
        if not items_dir.is_dir():
            return []
        return sorted(p.name for p in items_dir.iterdir() if p.is_dir())

    @classmethod
    def length(cls) -> int:
        return len(cls.keys())

    @classmethod
    def set(cls, key: str) -> Path:
        """Create `key`'s own entry if it doesn't already exist, seeded
        as a copy of the dummy head's own CURRENT content (its `.entry`
        and/or declared schema-child directories) — the "template" every
        entry structurally resembles, same idea as `Chain.insert()`'s
        own default (`paths=None`) behavior. A no-op, leaving whatever's
        already there alone, if `key` already exists — the copy only
        ever happens once, at the moment the key is actually created."""
        _validate_key(cls._topology_path(), key)
        target_dir = cls._items_dir() / key
        if target_dir.is_dir():
            return target_dir
        cls._entry_dir()  # ensure the dummy head has one too, for parity
        target_dir.mkdir(parents=True)
        copy_dir_contents(cls._assets_dir(), target_dir, exclude={_ITEMS})
        return target_dir

    @classmethod
    def pop(cls, key: str) -> None:
        """Remove `key`'s own entry outright — unlike `Chain.pop`,
        nothing else shifts (no other key's own identity changes), so
        this is a plain directory removal, not the two-rename dance
        `Chain` needs to preserve ordering."""
        from .._internal.fs import force_rmtree

        target_dir = cls._assets_dir() / _ITEMS / key
        if not target_dir.is_dir():
            raise TopologyValidationError(
                f"{cls._topology_path()} has no key {key!r}, nothing to pop"
            )
        force_rmtree(target_dir)

        from ..core.transform import invalidate_dict_key_cache  # local: avoid a cycle

        invalidate_dict_key_cache(cls._topology_path(), key)

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return _SYS_PROMPT

    @classmethod
    def on_child_moved(cls, old_child_stem: str, new_child_stem: str) -> None:
        """One of this dict's own schema children was renamed in place
        by `fatass move` — mirrors `Chain.on_child_moved`, but a flat
        glob over every key's own entry instead of a `.next`-depth walk,
        since entries here aren't nested."""
        items_dir = cls._assets_dir() / _ITEMS
        if not items_dir.is_dir():
            return
        for key_dir in items_dir.iterdir():
            if not key_dir.is_dir():
                continue
            old_dir = key_dir / old_child_stem
            if old_dir.is_dir():
                shutil.move(str(old_dir), str(key_dir / new_child_stem))

    def __getitem__(self, key: str) -> "_DictItem":
        if not (type(self)._assets_dir() / _ITEMS / key).is_dir():
            raise TopologyValidationError(
                f"{type(self)._topology_path()}[{key!r}] doesn't exist — "
                f"call .set({key!r}) first"
            )
        return _DictItem(type(self), key)


class _DictItem:
    """One resolved entry of a `Dictionary`. Mirrors `_ChainItem` almost
    exactly (see its own docstring for the shared reasoning) — the only
    real difference is the identity carried per entry: a `(dict_cls,
    key)` pair instead of `(list_cls, index)`, stamped under the SAME
    `_index_owner_cls`/`_index_key` names `_ChainItem` uses (not
    `Chain`-specific ones), so `NodeMeta.__getattr__`'s second-hop
    logic and `core.transform._resolve_dependency`'s sibling resolution
    work identically for a `Dictionary` item without needing to know
    which kind of collection it came from."""

    def __init__(self, dict_cls: type[Dictionary], key: str):
        self._dict_cls = dict_cls
        self._key = key

    def _assets_dir(self) -> Path:
        """This entry's own default content directory — for a leaf dict
        with no schema children declared, writing to the dict means
        writing here, e.g. `members["alice"]._assets_dir()`."""
        target_dir = self._dict_cls._assets_dir() / _ITEMS / self._key / _ENTRY
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def __getattr__(self, name: str):
        from ..core.transform import _import_node  # local import: avoid a cycle

        full_path = f"{self._dict_cls._topology_path()}.{name}"
        try:
            schema_cls = _import_node(full_path)
        except TopologyValidationError:
            raise AttributeError(name) from None

        index_home_dir = self._dict_cls._assets_dir() / _ITEMS / self._key / name
        is_new = not index_home_dir.is_dir()
        index_home_dir.mkdir(parents=True, exist_ok=True)

        namespace = {
            # See `_ChainItem.__getattr__`'s own docstring for why this
            # override is needed at all — the same reasoning applies
            # verbatim, just keyed by string instead of int.
            "_topology_path": classmethod(lambda cls, _p=full_path: _p),
            "_index_key": classmethod(lambda cls, _k=self._key: _k),
            "_index_owner_cls": classmethod(lambda cls, _dc=self._dict_cls: _dc),
            "_sibling": classmethod(
                lambda cls, sib_name: getattr(cls._index_owner_cls()()[cls._index_key()], sib_name)
            ),
            "_index_home_dir": classmethod(lambda cls, _d=index_home_dir: _d),
            "_parent_indexed": self,
        }
        has_custom_assets_dir = schema_cls._assets_dir.__func__ is not Node._assets_dir.__func__
        if has_custom_assets_dir:
            indexed_cls = type(f"{schema_cls.__name__}@{self._key}", (schema_cls,), namespace)
        else:
            namespace["_assets_dir"] = classmethod(lambda cls, _dir=index_home_dir: _dir)
            indexed_cls = type(f"{schema_cls.__name__}@{self._key}", (schema_cls,), namespace)
        if is_new:
            indexed_cls.on_created()
        return indexed_cls
