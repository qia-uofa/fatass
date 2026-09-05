import shutil
from pathlib import Path

from .._internal.fs import force_rmtree
from ..errors import TopologyValidationError
from .node import Node

_NEXT = ".next"
_ENTRY = ".entry"
_INSERT_TMP = ".next.insert-tmp"
_POP_TMP = ".next.pop-tmp"


def _copy_dir_contents(src: Path, dst: Path, *, exclude: set[str] = frozenset()) -> None:
    """Copy every child of `src` (skipping names in `exclude`) into
    `dst`, keeping each child's own basename. `dst` is assumed to already
    exist (created empty by the caller)."""
    if not src.is_dir():
        return
    for child in src.iterdir():
        if child.name in exclude:
            continue
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def _copy_paths_into(dst: Path, paths: list[Path]) -> None:
    """Copy each of `paths` (a real file or directory) into `dst`,
    keeping its own basename. `dst` is created if needed. Raises if two
    paths share a basename, or a path doesn't exist."""
    dst.mkdir(parents=True, exist_ok=True)
    for src in paths:
        if not src.exists():
            raise TopologyValidationError(f"{src} does not exist")
        target = dst / src.name
        if target.exists():
            raise TopologyValidationError(
                f"can't insert: {target} already exists — duplicate basename "
                f"{src.name!r} among the given paths"
            )
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)

_SYS_PROMPT = """## `Chain` — a dynamically-sized, indexable list of nodes

This node is (or should become) `class Node(fatass.Chain): pass` — a
homogeneous sequence whose length isn't known upfront (e.g. "one entry
per member"). Don't scaffold a new topology node per item — the whole
list is exactly one topology node. The actual items live entirely inside
this node's own `home/` directory as a recursive chain, never as new
topology nodes:

```
members/
  info/            ← dummy head: mirrors the schema, content always ignored (only if schema children are declared — see "structured lists" below)
  contribution/
  .entry/          ← dummy head's own default content — same reserved name an item has, also ignored by convention; exists only as `insert()`'s copy-source template
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
  isn't supported.
- `fatass len`/`insert`/`push`/`pop` (CLI, no agent call — deterministic
  `home/`-directory operations, like `.extend()`) manage list length and
  items directly: `len <node.path>` prints the current length; `push
  <node.path>` appends one item, seeded as a copy of the dummy head's own
  current content (its schema-child mirror directories and `.entry`) —
  the "template" every item structurally resembles; `insert <n>
  <node.path> [path1 path2 ...]` inserts at index `n` (shifting whatever
  was there, and everything after it, one slot back) — with explicit
  paths given (leaf lists only), the new item is seeded from exactly
  those files/directories instead of the dummy-head template; `pop
  <node.path> [n]` removes the tail (default) or item `n`, shifting
  anything after it forward. `members[*]` (in a `run`/`apply`/`build`/
  `free`/`sh`/`ls`/`vim` target) resolves to the current tail index —
  useful right after a `push` without having to re-read `len` first."""


class Chain(Node):
    """A `Node` whose actual content is a recursive, indexable chain
    living entirely inside its own `home/` directory — no new topology
    node is ever created as the list grows.

    The unindexed level (this class's own `_assets_dir()`) is a dummy
    head: whatever real topology children it declares (e.g. `info`,
    `contribution` — the per-item schema) exist there too, and it has its
    own `.entry` (`_entry_dir()`) same as a real item does — structurally
    identical to a normal item in every way, just that its content is
    never meaningful, only a mirror/template (see `insert()`'s dummy-copy
    variant). Presence of one `.next` directory means length >= 1;
    `members[i]` descends into `.next` exactly `i + 1` times. This avoids
    ever having to decide whether the base level's own content "counts"
    as an item — it never does, by convention.

    A list with no declared schema children (a "leaf" list) has nowhere
    else to put an item's content, so `_ChainItem._assets_dir()`
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
    def _entry_dir(cls) -> Path:
        """The dummy head's own `.entry` — structurally identical to a
        real item's `_ChainItem._assets_dir()` (same reserved name, at
        the unindexed depth), so the dummy head is exactly like a normal
        item, just ignored by convention: `insert()`'s dummy-copy variant
        uses this as its copy source for a leaf list, same as it uses the
        dummy head's schema-child mirror directories for a structured
        one."""
        target_dir = cls._assets_dir() / _ENTRY
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @classmethod
    def _has_schema_children(cls) -> bool:
        # Local import: topology_ops.scaffold imports core.free, which
        # only reaches back into topology_ops.scaffold via a matching
        # local import of its own — importing scaffold at module level
        # here would risk the same cycle.
        from ..topology_ops.scaffold import _all_node_paths

        own_path = cls._topology_path()
        prefix = f"{own_path}."
        return any(
            p.startswith(prefix) and "." not in p[len(prefix) :] for p in _all_node_paths()
        )

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
    def insert(cls, index: int, *, paths: list[Path] | None = None) -> Path:
        """Insert a new item at `index` (0..length(), inclusive — `index
        == length()` is a plain append, same as `extend()`), shifting
        whatever was already at `index` (and everything after it) one
        slot back.

        Because each `.next` directory *is* the rest of the chain from
        that point on (item `i`'s own content sits alongside the `.next`
        subdirectory that holds items `i+1..`), the shift is two renames
        of one subtree, not a per-item copy: the old chain starting at
        `index` is moved aside, a fresh slot is created and populated,
        then the old chain is reattached as that slot's own `.next` —
        O(1) regardless of list length or how many items follow `index`.

        `paths=None` (the default) populates the new slot as a copy of
        the dummy head's own current content (`_entry_dir()` plus every
        declared schema child's mirror directory) — the "template" every
        item structurally resembles. `paths=[...]` instead seeds the new
        slot directly from those files/directories (only valid for a
        *leaf* list — a structured list has no single directory to drop
        arbitrary files into; raises TopologyValidationError otherwise),
        copied in by their own basenames into the new item's `.entry`.

        Raises if `index` is out of range, or if a previous insert/pop
        appears to have failed partway (a leftover temp directory)."""
        length = cls.length()
        if not (0 <= index <= length):
            raise TopologyValidationError(
                f"{cls._topology_path()}: insert index {index} out of range "
                f"(length is {length}, valid indices are 0..{length})"
            )
        if paths is not None and cls._has_schema_children():
            raise TopologyValidationError(
                f"{cls._topology_path()}: insert with explicit paths is only "
                f"supported for a leaf list (no declared schema children) — "
                f"this list is structured; use `insert {index} "
                f"{cls._topology_path()}` (no paths) to seed the new item "
                f"from the dummy head's template, then populate its schema "
                f"children individually"
            )

        slot = cls._depth_dir(index)
        tmp = slot.parent / _INSERT_TMP
        has_existing = slot.is_dir()
        if has_existing:
            if tmp.exists():
                raise TopologyValidationError(
                    f"{tmp} already exists — a previous insert/pop on "
                    f"{cls._topology_path()} may have failed partway; "
                    f"remove it by hand before retrying"
                )
            slot.rename(tmp)
        slot.mkdir(parents=True)
        # Deliberately no try/finally around the copy below: if it fails
        # partway, reattaching `tmp` regardless would silently splice the
        # old chain onto a half-populated new item instead of surfacing
        # the failure. Leaving `tmp` in place lets the next call's
        # leftover-temp-directory check catch it instead.
        if paths is None:
            cls._entry_dir()  # ensure the dummy head has one too, for parity
            # Exclude the tmp names too, not just `.next`: when index == 0,
            # `slot.parent` IS `cls._assets_dir()`, so the just-renamed-aside
            # old chain (`tmp`) is sitting directly in it as a sibling next
            # to the dummy head's real content — without this it would get
            # swept into the copy as bogus extra content of the new item.
            _copy_dir_contents(
                cls._assets_dir(), slot, exclude={_NEXT, _INSERT_TMP, _POP_TMP}
            )
        else:
            _copy_paths_into(slot / _ENTRY, paths)
        if has_existing:
            tmp.rename(slot / _NEXT)

        # Always invalidate from `index` on — even a plain append (index ==
        # length) could collide with a stale entry left behind by an
        # earlier pop that emptied and never reused that index number.
        from ..core.transform import invalidate_index_cache  # local: avoid a cycle

        invalidate_index_cache(cls._topology_path(), index)
        return slot

    @classmethod
    def pop(cls, index: int | None = None) -> None:
        """Remove item `index` (default: the last item — the tail), same
        O(1) two-rename shift as `insert()`, in reverse: the removed
        item's own content is dropped, and whatever chain continued past
        it (if any) is reattached in its place."""
        length = cls.length()
        if length == 0:
            raise TopologyValidationError(f"{cls._topology_path()} is empty, nothing to pop")
        if index is None:
            index = length - 1
        if not (0 <= index < length):
            raise TopologyValidationError(
                f"{cls._topology_path()}: pop index {index} out of range "
                f"(length is {length})"
            )

        slot = cls._depth_dir(index)
        next_slot = slot / _NEXT
        if next_slot.is_dir():
            tmp = slot.parent / _POP_TMP
            if tmp.exists():
                raise TopologyValidationError(
                    f"{tmp} already exists — a previous insert/pop on "
                    f"{cls._topology_path()} may have failed partway; "
                    f"remove it by hand before retrying"
                )
            next_slot.rename(tmp)
            force_rmtree(slot)
            tmp.rename(slot)
        else:
            force_rmtree(slot)

        # Always invalidate from `index` on — including the tail case
        # (index == length - 1): its own now-stale entry should go too,
        # in case that number gets reused by a later insert/push.
        from ..core.transform import invalidate_index_cache  # local: avoid a cycle

        invalidate_index_cache(cls._topology_path(), index)

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

    def __getitem__(self, index: int) -> "_ChainItem":
        length = type(self).length()
        if not (0 <= index < length):
            raise TopologyValidationError(
                f"{type(self)._topology_path()}[{index}] is out of range "
                f"(length is {length})"
            )
        return _ChainItem(type(self), index)


class _ChainItem:
    """One resolved item of a `Chain`. Attribute access resolves a
    real topology child of the list node (e.g. `.info`) to a dynamically
    derived subclass of that child's real class, with `_assets_dir()`
    overridden to this item's depth instead of the literal (dummy-head)
    topology path. The item itself also has its own `_assets_dir()`
    (below), resolving to a reserved `.entry` directory at this depth —
    the default place to write when the list has no schema children.
    Everything downstream (`free()`'s `readable=[...]`, `validate_node`,
    caching) keeps working unmodified either way — they only ever call
    `._assets_dir()`, duck-typed, never check class identity."""

    def __init__(self, list_cls: type[Chain], index: int):
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
        from ..core.transform import _import_node  # local import: avoid a cycle

        full_path = f"{self._list_cls._topology_path()}.{name}"
        schema_cls = _import_node(full_path)

        target_dir = self._list_cls._depth_dir(self._index) / name
        target_dir.mkdir(parents=True, exist_ok=True)

        return type(
            f"{schema_cls.__name__}@{self._index}",
            (schema_cls,),
            {"_assets_dir": classmethod(lambda cls, _dir=target_dir: _dir)},
        )
