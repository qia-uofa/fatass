from pathlib import Path

from ..errors import TopologyValidationError
from .node import Node

_NEXT = ".next"

_SYS_PROMPT = """## `NodeList` — a dynamically-sized, indexable list of nodes

This node is (or should become) `class Node(fatass.NodeList): pass` — a
homogeneous sequence whose length isn't known upfront (e.g. "one entry
per member"). Don't scaffold a new topology node per item — the whole
list is exactly one topology node, with its per-item fields (e.g.
`info`, `contribution`) declared as *its own* ordinary child nodes, same
as any node's children. The actual items live entirely inside this
node's own `home/` directory as a recursive chain, never as new topology
nodes:

```
members/
  info/           ← dummy head: mirrors the schema, content always ignored
  contribution/
  .next/          ← reserved name, never a topology node — presence means length >= 1
    info/         ← members[0].info
    contribution/ ← members[0].contribution
    .next/        ← presence means length >= 2
      ...
```

- `.extend()` adds one more `.next` level at the current tail (a pure
  `home/`-directory operation — it never touches `fatass/topology/`).
- `members[i]` raises if `i` is out of range for the current length —
  growing only ever happens via an explicit `.extend()`, never as a side
  effect of indexing.
- `fatass run`/`apply`/`build` can target a specific item directly, e.g.
  `fatass run "members[2].info"` (quote it — `[`/`]` are shell-glob
  characters) — this runs `info`'s own `build()` transform scoped to that
  item's `home/` subdirectory, cached independently per index.
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

    def __getitem__(self, index: int) -> "_NodeListItem":
        length = type(self).length()
        if not (0 <= index < length):
            raise TopologyValidationError(
                f"{type(self)._topology_path()}[{index}] is out of range "
                f"(length is {length})"
            )
        return _NodeListItem(type(self), index)


class _NodeListItem:
    """One resolved item of a `NodeList` — attribute access resolves a
    real topology child of the list node (e.g. `.info`) to a dynamically
    derived subclass of that child's real class, with `_assets_dir()`
    overridden to this item's depth instead of the literal (dummy-head)
    topology path. Everything downstream (`free()`'s `readable=[...]`,
    `validate_node`, caching) keeps working unmodified — they only ever
    call `._assets_dir()`, duck-typed, never check class identity."""

    def __init__(self, list_cls: type[NodeList], index: int):
        self._list_cls = list_cls
        self._index = index

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
