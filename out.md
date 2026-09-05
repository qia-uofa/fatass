## `Chain` — a dynamically-sized, indexable list of nodes

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
  useful right after a `push` without having to re-read `len` first.