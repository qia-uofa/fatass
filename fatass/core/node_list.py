import shutil
from pathlib import Path

from ..errors import TopologyValidationError
from .node import Node

_NEXT = ".next"
_ENTRY = ".entry"

_SYS_PROMPT = """## `NodeList` — a dynamically-sized, indexable list of nodes

This node is (or should become) `class Node(fatass.NodeList): pass` — a
homogeneous sequence whose length isn't known upfront (e.g. "one entry
per member"). Don't scaffold a new topology node per item — the whole
list is exactly one topology node. The actual items live entirely inside
this node's own `home/` directory as a recursive chain, never as new
topology nodes:

```
members/
  info/            ← dummy head: mirrors the schema, content always ignored (only if schema children are declared — see "structured lists" below)
  contribution/
  .next/           ← reserved name, never a topology node — presence means length >= 1
    info/          ← members[0].info (only if schema children are declared)
    contribution/  ← members[0].contribution
    .entry/        ← members[0]'s own default content — reserved name, for a "leaf" list (see below); members[0]._assets_dir()
    .next/         ← presence means length >= 2
      .entry/      ← members[1]'s own default content — members[1]._assets_dir()
      ...
```

- `.extend()` and `.length()` are classmethods, called directly on the
  list class itself (`Members.extend()`, `Members.length()`) — no
  instance needed. `.extend()` adds one more `.next` level at the
  current tail (a pure `home/`-directory operation — it never touches
  `fatass/topology/`).
- Indexing (`members[i]`) needs an *instance* (`members = Members()`),
  not the class — `__getitem__` is an instance method, separate from the
  `.extend()`/`.length()` classmethods above. It raises if `i` is out of
  range for the current length — growing only ever happens via an
  explicit `.extend()`, never as a side effect of indexing.
- **Leaf lists — the common case, one thing per item, no further
  structure:** don't declare any schema children at all. Just index and
  write: `members[i]._assets_dir()` resolves straight to a reserved
  `.entry` directory at that item's depth (`members[1]` → `.next/.next/
  .entry`), creating it lazily on first access — no manual `mkdir`
  needed, and no need to scaffold a real "entry" node just to have
  somewhere to write. The usual pattern, inside the list's own `build()`
  transform:

  ```python
  for item_data in ...:
      result = fatass.free(readable=[...], returns=str, silent=True, prompt=...)
      Members.extend()
      target_dir = members[Members.length() - 1]._assets_dir()
      (target_dir / "output.md").write_text(result, encoding="utf-8")
  ```

  `fatass.free()`'s writable directory is always the *list node's own*
  (dummy-head) `home/` directory — same as for any other node's
  transform — never a specific item's directory; there's no way to scope
  a `free()` call's writes to `members[i]` directly. Capture the agent's
  result via `returns=...` and persist it into the item's `.entry`
  yourself with plain file I/O, as above.
- **Structured lists — each item needs more than one named field (e.g.
  `info` *and* `contribution`):** declare the per-item schema as the
  list's own ordinary child nodes, same as any node's children.
  `members[i].<schema_child>` (e.g. `members[i].info`) then resolves to
  that item's own version of the schema child, creating its directory on
  first access — same lazy-creation, same write-it-yourself pattern as
  `.entry` above, just one directory per declared field instead of one
  shared `.entry`. This is a design recommendation, not an enforced
  constraint: `.entry` still exists and is still writable even on a
  structured list, but by convention a structured list just doesn't use
  it — and if schema children are added later to a list that started out
  using `.entry`, any existing `.entry` content is simply left alone,
  unused, never migrated.
- `fatass run`/`apply`/`build` can target a specific item's schema child
  directly, e.g. `fatass run "members[2].info"` (quote it — `[`/`]` are
  shell-glob characters) — this runs `info`'s own `build()` transform (if
  it has one) scoped to that item's `home/` subdirectory, cached
  independently per index. This only applies to a declared schema child
  (there's no transform to run against `.entry`) — it's a separate,
  per-item-driven way to populate a structured list's items, an
  alternative to, not required alongside, growing and writing everything
  from the list's own `build()` as above.
- A schema child's own dependencies (e.g. `contribution` depending on
  something) should point outside its own list — same-item
  cross-referencing (e.g. `contribution` reading the same item's `info`)
  isn't supported."""


class NodeList(Node):
    """A `Node` whose actual content is a recursive, indexable chain
    living entirely inside its own `home/` directory — no new topology
    node is ever created as the list grows.

    The unindexed level (this class's own `_assets_dir()`) is a dummy
    head: whatever real topology children it declares (e.g. `info`,
    `contribution` — the per-item schema) exist there too, but their
    content at that literal path is never meaningful, only a mirror of
    the schema. Presence of one `.next` directory means length >= 1;
    `members[i]` descends into `.next` exactly `i + 1` times. This avoids
    ever having to decide whether the base level's own content "counts"
    as an item — it never does, by convention.

    A list with no declared schema children (a "leaf" list) has nowhere
    else to put an item's content, so `_NodeListItem._assets_dir()`
    resolves each item straight to a reserved `.entry` directory at its
    depth instead — see that method for details.
    """

    @classmethod
    def _depth_dir(cls, index: int) -> Path:
        path = cls._assets_dir()
        for _ in range(index + 1):
            path = path / _NEXT
        return path

    @classmethod
    def length(cls) -> int:
        path = cls._assets_dir()
        count = 0
        while (path / _NEXT).is_dir():
            count += 1
            path = path / _NEXT
        return count

    @classmethod
    def extend(cls) -> Path:
        """Add one more `.next` level at the current tail. Only creates
        that directory itself — per-item schema folders (e.g. `info`)
        are created lazily on first access, not eagerly here."""
        path = cls._assets_dir()
        while (path / _NEXT).is_dir():
            path = path / _NEXT
        new_path = path / _NEXT
        new_path.mkdir(parents=True)
        return new_path

    @classmethod
    def create_sys_prompt(cls) -> str | None:
        return _SYS_PROMPT

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return _SYS_PROMPT

    @classmethod
    def on_child_moved(cls, old_child_stem: str, new_child_stem: str) -> None:
        """One of this list's own schema children (e.g. `sidenote`) was
        renamed in place by `fatass move` — `move_node`'s own generic move
        already relocated the schema child's dummy-head directory (this
        list's own home/ directory has an `<old_child_stem>` mirror, same
        as any other node's child), but the real per-item content lives
        inside every existing `.next` level (see this class's own
        docstring), which `move_node` has no notion of. Rename the matching
        subdirectory at every depth that has one, so existing items keep
        their content under the new name instead of it going orphaned
        under the old one."""
        path = cls._assets_dir()
        while (path / _NEXT).is_dir():
            path = path / _NEXT
            old_dir = path / old_child_stem
            if old_dir.is_dir():
                shutil.move(str(old_dir), str(path / new_child_stem))

    def __getitem__(self, index: int) -> "_NodeListItem":
        length = type(self).length()
        if not (0 <= index < length):
            raise TopologyValidationError(
                f"{type(self)._topology_path()}[{index}] is out of range "
                f"(length is {length})"
            )
        return _NodeListItem(type(self), index)


class _NodeListItem:
    """One resolved item of a `NodeList`. Attribute access resolves a
    real topology child of the list node (e.g. `.info`) to a dynamically
    derived subclass of that child's real class, with `_assets_dir()`
    overridden to this item's depth instead of the literal (dummy-head)
    topology path. The item itself also has its own `_assets_dir()`
    (below), resolving to a reserved `.entry` directory at this depth —
    the default place to write when the list has no schema children.
    Everything downstream (`free()`'s `readable=[...]`, `validate_node`,
    caching) keeps working unmodified either way — they only ever call
    `._assets_dir()`, duck-typed, never check class identity."""

    def __init__(self, list_cls: type[NodeList], index: int):
        self._list_cls = list_cls
        self._index = index

    def _assets_dir(self) -> Path:
        """This item's own default content directory (reserved name,
        coexists with `.next` at this depth) — for a "leaf" list with no
        schema children declared, writing to the list means writing here,
        e.g. `members[Members.length() - 1]._assets_dir()`. Still
        created and usable even when schema children exist (nothing
        enforces "leaf-only"); by convention a list with schema children
        just doesn't use it, same as the dummy head's own content being
        ignored by convention rather than by any check."""
        target_dir = self._list_cls._depth_dir(self._index) / _ENTRY
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def __getattr__(self, name: str):
        from .transform import _import_node  # local import: avoid a cycle

        full_path = f"{self._list_cls._topology_path()}.{name}"
        schema_cls = _import_node(full_path)

        target_dir = self._list_cls._depth_dir(self._index) / name
        target_dir.mkdir(parents=True, exist_ok=True)

        return type(
            f"{schema_cls.__name__}@{self._index}",
            (schema_cls,),
            {"_assets_dir": classmethod(lambda cls, _dir=target_dir: _dir)},
        )
