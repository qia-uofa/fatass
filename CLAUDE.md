# fatass

fatass synthesizes and manages project files using the Claude CLI as an
agent. A project is a graph of **nodes**: each has a Python definition
under `fatass/topology/` (a `Node` subclass, named after the node itself,
in `<name>.py`) mirrored by an asset directory under `home/`. Transform
files sit directly alongside it in the same directory — plain functions
whose `Node`-typed parameters declare dependencies on other nodes; calling
one invokes `fatass.free(...)`, which runs the Claude CLI as a subprocess,
reading dependency nodes' directories and writing into the node's own.

Full design docs: [blueprint/](blueprint/README.md).

## CLI

```
python -m fatass run <node.path>[.transforms.<name>] [--force]   # run transform(s), cache-aware
python -m fatass apply <transform>@<node.path> [key=value ...]    # run one transform with explicit args, ignoring cache
python -m fatass create <node.path | transform@node.path>[(NodeSubclass)]  # scaffold if missing; e.g. members(Chain) subclasses fatass.Chain instead of fatass.Node; an Array subclass also takes ,dim=<int>x<int>x... e.g. grid(ArrayTxt,dim=2x2x2)
python -m fatass create <transform>(<dep.path>[,<dep.path> ...])@<node.path>   # scaffold a transform and bind the given deps onto it in the same call (no agent call for the binding — same as a `bind` right after)
python -m fatass modify <node.path | transform@node.path> ["..."] [--silent] [--permission-mode M] [--model M]    # edit an existing node/transform file; prompt is positional and optional — omitted or "" both become the literal text "<no instructions given — wait for further input>"
python -m fatass debug <transform>@<node.path> ["..."] [--silent] [--permission-mode M] [--model M]    # like modify, but framed around root-causing a failure: inlines the relevant tail of ./log for this transform (past dispatches and free() calls' args/exit codes/stdout/stderr) plus a tail of `fatass shell`'s own persisted `>>> ` command history (.fatass/shell_history — not the OS terminal's), and grants read access to only the transform's input (declared dependency) and output (home/) nodes
python -m fatass move <node.path> <new.node.path>                 # move/rename a node, rewriting references
python -m fatass copy <node.path> <new.node.path>                 # copy a node, rewriting the copy's internal references
python -m fatass remove <node.path | transform@node.path>         # remove a node (and nested nodes) or one transform
python -m fatass purge <node.path> [-rs] [-rd] [-rsd]              # empty a node's home/ content (see command docs for flags)
python -m fatass archive [name] [--node <node.path>]                # move topology/home under ./archive/ and start fresh, or (with --node) archive just that node's subtree in place
python -m fatass retrieve [name] [--node <node.path>]               # restore an archived topology/home snapshot, or (with --node, requires a named archive) just that node back to its original path
python -m fatass build <node.path> [key=value ...]                 # shorthand for `apply build@<node.path>`
python -m fatass free <target> ["..."] [--silent] [--permission-mode M] [--model M]  # ad-hoc agent call scoped to a resolved target's directory; prompt is positional and optional, same "<no instructions given — wait for further input>" fallback as modify
python -m fatass sh <target> <command...>                          # run a shell command, cwd resolved from target
python -m fatass cd <expr>                                          # change the current node (FATASS_NODE)
python -m fatass pwd                                                # print the current node (FATASS_NODE)
python -m fatass graph [node.path] [-o/--output ...]                # write a PlantUML diagram of node inclusion + transform dependencies, rooted at node.path (default: whole topology)
python -m fatass ls [-r] <node.path | node.path/rel/path | transform@node.path>  # show a node's own class + subnodes + transforms (each with its dependencies' classes/subnodes), or a raw directory listing for a '/'/'@' target; -r recurses into the full inclusion/directory tree instead of one level
python -m fatass bind [-a/--absolute] <transform>@<node.path> [dep.path ...]    # add nodes as declared Node-typed dependencies on a transform (no agent call); -a replaces the whole dependency set instead of adding to it (unbinds everything first) — with no dep.path at all, -a just clears every existing bind
python -m fatass unbind <transform>@<node.path> <dep.path> [dep.path ...]  # remove nodes from a transform's declared dependencies (no agent call)
python -m fatass len <node.path>                                    # print a Chain's current length (no agent call)
python -m fatass push <node.path>                                   # append one item to a Chain, seeded as a copy of the dummy head's own content (no agent call)
python -m fatass insert <n> <node.path> [path1 path2 ...]           # insert an item into a Chain at index n, shifting the rest back; with no paths, seeds from a copy of the dummy head's content, else from those files/dirs (leaf lists only — each path is either an absolute real filesystem path, or a fatass target expression) (no agent call)
python -m fatass pop <node.path> [n]                                # remove a Chain's tail item, or item n if given, shifting anything after it forward (no agent call)
python -m fatass vim <node.path | transform@node.path | node.path(rel/path)>  # open a node's class file, a transform file, or a home/ file in vim
python -m fatass shell                                              # interactive REPL, one command per line
```

Node/transform paths are `.`-separated, matching Python module addressing
(`node1.node2`, `node1.node2.transforms.synthesize`).

`sh`, `free`, and `ls`'s `(`/`@` targets share one `<target>` grammar
(`fatass.resolve.targets.resolve`): `node1.node2` (that node's own
directory under `fatass/topology/`), `transform@node1.node2` (that same
node directory too — a transform file sits directly in it, no separate
subdirectory), or `node1.node2(dir1/dir2/file.txt)` (a path relative to the node's `home/`
assets directory — `node1.node2()`, `node1.node2(.)`, or `node1.node2(./)`
name that directory itself; a file path resolves to its parent dir). The
node-path portion before the first `(` must be non-empty — a target
starting with `(` is rejected rather than silently resolving against the
current node, since an unquoted `~/rel/path` gets shell-tilde-expanded
into an absolute filesystem path (dropping the leading `~` entirely)
before fatass ever sees the argument; write `~.` (or quote the argument)
for an explicit root-relative target.

An empty call, `node1.node2()`, means "the home dir itself" for an
ordinary `Node`/`Chain` — but a `Single`/`Array` node (see below)
overrides what a *bare* `()` means: on a `Single` it resolves straight to
that node's one managed file instead; on an `Array`, `node1.node2()`
alone still means the home dir, but `node1.node2()[i,j,...]` resolves to
the file at that index. Giving an explicit path inside the parens (e.g.
`node1.node2(.)` for the home dir on a `Single`) behaves identically
across every subclass — only the empty-call shorthand's meaning depends
on the node's class. This composes with `Chain`'s own `node[i]` item
indexing (always on the bare node, before any `(`) rather than
conflicting with it: `members[i]()` resolves item `i`'s own home dir/file
the same way, per that item's own schema child's class.

`ls`'s bare `node1.node2` form (no `(`
or `@`) doesn't resolve through this — it takes the fast path in
`fatass/ls.py:list_node`, which imports the node itself (via
`fatass.core.transform._import_node`) to get its *base* fatass class
(`"Node"` or `"Chain"` — not its own specific subclass name, which is
just the PascalCase of its own path segment and adds no information the
path doesn't already carry), plus its direct subnodes (from
`fatass.topology_ops.scaffold._all_node_paths`) and its own transforms
(from `fatass.core.transform.discover`) instead of a raw directory
listing. `fatass ls`'s printed form reads like Python's own
declare-then-assign shape: `name : ClassName(...)` for "this is the
node" (bare own name — it's obviously *this* node, so no `~.` path
prefix) and `name = transform(...)` for "this is how it's built", with a
transform's dependencies shown the same `:` node-definition shape one
level deep — but full-path-addressed (`~.<path>`), since a dependency
can live anywhere in the topology, not just under the node being listed:

```
summaries : Chain(entry)
summaries = build(
    ~.tests.list.article : Node(),
)
```

The root (`fatass ls ~`, no node file of its own) prints the same shape
using the synthetic class name `topology` (matching `graph`'s root
label): `~ : topology(cv, examples, roster, tests)`. A transform named
`build` is always sorted first among a node's transforms — the
conventional entry point — with the rest kept in `discover()`'s
alphabetical-by-filename order.

`-r` recurses instead of showing just one level. For the structured
(non-`:`/`@`) form, `fatass.ls.list_node_tree`/`list_root_tree` walk the
*whole* inclusion subtree (no depth limit, no transforms — just the
`name : ClassName(...)` shape nested arbitrarily deep, each child
indented four spaces further and comma-terminated):

```
tests : Node(
    list : Node(
        article : Node(),
        summaries : Chain(
            entry : Node(),
        ),
    ),
)
```

For a `(`/`@` target, `-r` instead walks the real filesystem tree
(`fatass.ls.list_dir_tree`), same trailing-`/`-for-directories convention
as the non-`-r` form, each nesting level indented four spaces further.

`vim` uses the same grammar but through a sibling function,
`fatass.resolve.targets.resolve_file`, which keeps the actual file instead
of collapsing it to its parent directory: `node1.node2` opens that node's
own `<name>.py` class file, `transform@node1.node2` opens that transform's
`.py` file, and `node1.node2(rel/path)` opens that path under the node's
`home/` directory (need not already exist — vim creates it on save, same
as `vim newfile.txt` at a shell). `node1.node2()` on a `Single` node opens
its one managed file directly; `node1.node2()[i,j,...]` on an `Array`
node opens the file at that index.

### `Chain`

`fatass.Chain` (`fatass/core/chain.py`) represents a dynamically-
sized, homogeneous sequence without creating a new topology node per
item — the topology stays fully static (still one `<name>.py` per real
node, still discoverable by walking the filesystem before any code
runs). A list can be either **structured** — one real node
(`class Members(fatass.Chain): pass`) declares the per-item schema as
its own ordinary children (e.g. `members.info`, `members.contribution` —
real nodes, can have their own `build()`) — or a **leaf** — no schema
children declared at all, just one thing per item. Either way every
actual item lives entirely inside `members`'s own `home/` directory as a
recursive `.next` chain:

```
members/
  info/            <- dummy head: mirrors the schema, content always ignored (structured lists only)
  contribution/
  .next/           <- reserved name, never a topology node; presence means length >= 1
    info/          <- members[0].info (structured lists only)
    contribution/  <- members[0].contribution
    .entry/        <- members[0]'s own default content (leaf lists) — members[0]._assets_dir()
    .next/         <- presence means length >= 2
      .entry/      <- members[1]'s own default content — members[1]._assets_dir()
      ...
```

- `Members.extend()` adds one more `.next` level at the current tail — a
  pure `home/`-directory operation (`mkdir`), never touching
  `fatass/topology/`.
- `Members.length()` counts existing `.next` levels (0 = empty).
- `members_instance[i]` (`Chain.__getitem__`) raises
  `TopologyValidationError` naming the current length if `i` is out of
  range — growing only ever happens via an explicit `.extend()`, never as
  a side effect of indexing or reading.
- **Leaf lists:** `members[i]._assets_dir()` (`_ChainItem._assets_dir()`)
  resolves straight to a reserved `.entry` directory at that item's depth
  — e.g. `members[1]` -> `members/.next/.next/.entry` — creating it
  lazily on first access. This is the default place to write when a list
  has no schema children, so a plain per-item value no longer needs a
  scaffolded "entry" node just to have somewhere to live.
- **Structured lists:** `members[i].info` resolves to a dynamically
  derived subclass of the real `Info` node class, with `_assets_dir()`
  overridden to the depth-`i` path — `free()`'s `readable=[...]`,
  `validate_node`, and caching all keep working unmodified, since they
  only ever call `._assets_dir()`, duck-typed. `.entry` still exists and
  is still writable on a structured list too (nothing enforces
  "leaf-only" — it's a design recommendation, not a constraint), but by
  convention a structured list just doesn't use it; adding schema
  children to a list that started out using `.entry` leaves any existing
  `.entry` content alone, unused, never migrated.
- `run`/`apply`/`build` accept an indexed target directly, e.g. `fatass
  run "members[2].info"` (quote it — `[`/`]` are shell-glob characters in
  some shells) — `core/transform.py`'s `_split_index`/`_resolve_owning_node`
  parse the bracket, resolve the item, and cache the result independently
  per index (`discover()` itself still reflects on the *real*,
  index-independent node's own package directory). This targets a
  declared schema child's own transform, so it doesn't apply to `.entry`
  (there's no transform to run there).
- `sh`/`free`/`ls`/`vim`'s `/`/`@` target grammar (`fatass.resolve.targets`)
  understands an indexed segment too, e.g. `fatass free "members[2]/rel/path"`
  or `transform@members[2].info` — for the `/` form this resolves straight
  to that item's (or schema child's) own `home/` directory, unlike
  `run`/`apply`/`build` a *bare* indexed item with no schema-child suffix
  is valid here (`members[2]` alone resolves to that item's own `.entry`);
  for the `@` form the index is bounds-checked but the returned directory
  is always the shared, real topology directory, since a schema child's
  code is the same file for every item. The bare (no `/`, no `@`) form
  rejects an indexed target outright — an item has no topology directory
  of its own. `create`/`modify`/`move`/`remove`/`bind`/`unbind`/`graph`
  still don't understand indexed targets at all (nothing there is
  per-item — a schema child's topology definition is shared).
- `[*]` (in place of a literal index, anywhere the above accept one)
  means "the current tail" — `length() - 1`, resolved at the time of the
  call (raises if the list is empty). Handy right after a `push` without
  having to `len` first, e.g. `fatass run "members[*].info"`.
- Not supported: a schema child depending on a sibling schema child in
  the same item (e.g. `contribution` reading the same item's `info`) does
  not auto-resolve to the same index — schema-node dependencies should
  point outside their own list.

### `Single` / `Array`

`fatass.Single` (`fatass/core/single.py`) and `fatass.Array`
(`fatass/core/array.py`) manage a fixed, deterministic set of plain files
directly under a node's own `home/` directory — no arbitrary
agent-written content, no dynamic growth (unlike `Chain`).

- **`Single`** manages exactly one file, named `_` (or `_<EXT>` for a
  typed subclass — `SingleTxt` -> `_.txt`, `SinglePdf` -> `_.pdf`).
  `Single.write(content: str)` writes straight to it, creating the file
  (and the node's `home/` dir) first if either doesn't exist yet — never
  raises for a missing file. `fatass purge` on a `Single` node clears the
  file in place instead of deleting it (a no-op, not an error, if the
  file doesn't currently exist).
- **`Array`** manages a fixed-shape grid of files, one per index in
  `range(DIM[0]) x range(DIM[1]) x ...`, named `_<i>_<j>_...` (or
  `_<i>_<j>_...<EXT>` for a typed subclass — `ArrayTxt`, `ArrayPdf`).
  `DIM` is a tuple declared on the concrete node subclass, e.g.
  `class Grid(fatass.ArrayTxt): DIM = (2, 2, 2)`. `Array.write([i, j,
  ...], content: str)` writes to the file at that index, same
  create-if-missing behavior as `Single.write`. `fatass purge` clears
  whichever files currently exist in place, silently skipping any that
  are missing (never raises, never creates one just to purge it).
- `fatass create <node.path>(SingleTxt)` etc. scaffolds a `Single`
  subclass the same way as any other `(NodeSubclass)` target. An `Array`
  additionally needs `DIM` known *before* its files can be created, so
  the create-target grammar accepts an extra `,dim=<int>x<int>x...`
  (`x`-separated, not comma-separated — that would collide with the
  outer `(NodeSubclass,...)` split), e.g. `fatass create
  grid(ArrayTxt,dim=2x2x2)` — this is baked into the generated class
  as `DIM = (2, 2, 2)` instead of a bare `pass` body
  (`scaffold.create_node`'s `class_kwargs`).
- Both override `Node.on_created()` — a hook, no-op on plain `Node`,
  that `fatass create` calls (via `CreateCommand.after_reload`, once the
  topology tree has been reloaded and the new class is actually
  importable) right after scaffolding a node — to touch their managed
  file(s) into existence blank immediately, rather than waiting for
  first access. This is why `Array`'s shape has to be known at create
  time: `on_created()` needs `DIM` to know which files to create.
- Both override `Node.purge_self()` — a hook, `None` by default (meaning
  "no override, use `fatass purge`'s generic delete-everything-in-this-
  node's-own-home-dir behavior") — to clear their file(s) in place
  instead.
- **Transform convention:** a transform that populates a `Single`/`Array`
  node must never let `fatass.free(...)` write into that node's `home/`
  directory directly (e.g. via `writable=` or by just letting the agent
  edit files there) — capture the agent's result with `returns=str` and
  call `NodeClass.write(...)` (or `NodeClass.write([i, j, ...], ...)`)
  yourself instead. `Single`/`Array` teach this via their own
  `modify_sys_prompt()` override (same mechanism `Chain` uses for its own
  conventions), so editing a transform bound to one of these nodes gets
  this guidance appended automatically.
- Grammar sugar for direct access (see the `sh`/`free`/`ls`/`vim` target
  grammar above): `node.path()` on a `Single` resolves to its one managed
  file; `node.path()[i,j,...]` on an `Array` resolves to the file at that
  index. `node.path(.)` still reaches the home dir explicitly on either.

### `bind`/`unbind`

The deterministic (no agent call) alternative to `modify --prompt "add a
dependency on X"` for the purely mechanical part of that edit —
`fatass.topology_ops.bind.bind_transform`/`unbind_transform`. Given
`<transform>@<node.path>` and one or more dependency `node.path`
arguments, they add/remove the matching `Node`-typed parameter and its
`from fatass.topology.<path> import <Alias> as <Alias>` import on the
transform's function, using `ast` only to *locate* exact source
positions and then splicing text at just those positions — every other
byte of the file (in particular a transform's large f-string prompt) is
left untouched, unlike a naive `ast.parse` -> modify -> `ast.unparse`
round-trip, which would reformat the whole file.

- `bind` is idempotent (silently skips a dependency that's already
  bound) and validates every requested binding up front — a parameter-
  name collision against an existing, different-node parameter raises
  before anything is written, so one bad argument in a multi-node call
  never leaves the file half-edited. New parameters are inserted before
  any existing defaulted parameter (Python requires non-default
  parameters first), not blindly appended at the end.
- `unbind` raises if the dependency isn't currently bound, or if its
  parameter name is still referenced anywhere in the function body (e.g.
  still sitting in a `readable=[...]` list) — mirroring `remove_node`'s
  "still depended on" refusal, at the parameter level — and removes the
  import too if nothing else in the file still uses it.
- Neither touches a `fatass.free(...)` call's `readable=[...]` or the
  prompt text — actually wiring a newly bound parameter into a specific
  call and explaining why in the prompt is semantic content, left to a
  human or a follow-up `modify --prompt`.

### Current node (`FATASS_NODE`)

Every `<node.path>` argument anywhere in the CLI is resolved relative to
a **current node**, stored as `FATASS_NODE` in the dotenv file at
`.fatass/.env` (`fatass.resolve.cwd`) — no file, or no `FATASS_NODE` in it,
defaults to `~` (the sentinel for "no current node", i.e. the true
topology root). `cd` changes it, `pwd` prints it. One primitive,
`fatass.resolve.cwd.expand`, backs all of it: `fatass.resolve.targets.resolve` runs it
over the node-path portion of `sh`/`free` targets, and
`fatass.commands._targets.resolve_node_path` runs it (rejecting the `~`
sentinel — these all need a real node) for every node-path argument to
`run`/`apply`/`build`/`create`/`modify`/`move`/`remove`:

- A bare expression is prefixed with the current node: `node1.node2`
  resolves under it, exactly as before, when `FATASS_NODE` is unset.
- A leading `~` ignores the current node for an absolute path:
  `~.something` == `something`; `~` alone resolves to the root sentinel
  itself (rejected by things that need a real node, e.g. `transform@~`).
- A run of *N* consecutive dots ascends *N*-1 levels from wherever the
  walk currently stands, then descends into whatever follows: `.` stays
  put (the current node itself), `..` goes to its parent, `...` its
  grandparent, and `node1..node2` is "node1's parent's child node2"
  (siblings of node1, from the current node). Going above the root
  raises an error.

Every command that changes `fatass/topology/` itself
(`create`/`modify`/`move`/`remove`/`archive`/`retrieve`) reloads the
already-imported `fatass.topology` tree afterward (`cli.main()`, via
`fatass._internal.import_tree.reload_all`) — needed because `import fatass` eagerly
imports the whole tree once, and a long-lived process (the `shell` REPL
running several commands in a row) would otherwise keep seeing
`sys.modules` entries from before that command ran.

### `graph`

`fatass.graph.build_graph(root=None)` writes a PlantUML
(`@startuml`/`@enduml`) diagram: a flat `class` per node, each declared
inside a `together` block with its inclusion siblings (so they render at
the same layout level) and linked to its parent by a dotted
`child .up.> parent` arrow — this draws the inclusion relation. One arrow
per transform dependency — `dependency --> owner : transform_name`, bold
for the `build` transform, unlabeled when the transform is named `build`
(every node has one, so the label is redundant) — draws the dependency
relation, pointing from the dependency into the node whose transform
reads it; an edge between
tree-unrelated nodes gets a `right` direction hint so it doesn't disturb
the inclusion layout. A transform with no `Node`-typed dependency draws
from a special `"None"` node instead.

With no `root` (`graph` with no node argument), the whole topology is
drawn and the root class is `"topology"`. With `root` given (`graph
<node.path>`, resolved relative to the current node like any other
node-path argument), only that node and its descendants are drawn — the
root class is labeled with its full dotted path instead of just its last
segment, since it has no rendered parent to make that path implicit — and
a transform dependency on a node *outside* that subtree is drawn as a
single flat class labeled with its own full path (like the `"None"`
node), rather than pulling in that node's ancestry too.

`write_graph(output, root=None)` writes to `output` if given, else to
`./<root>.puml` (or `./topology.puml` when `root` is `None`) in the
current working directory.

### Agent calls: silent vs. interactive, permission mode, system prompts

`_invoke_claude` (`fatass/core/free.py`) is the single subprocess choke
point behind `fatass.free()`, `free_topology()` (`create`/`modify`), and
`free_at()` (`fatass free`) — every path that actually shells out to the
real `claude` CLI goes through it, and it takes four orthogonal knobs:

- **`silent`** (default `False`): when false, opens a real, human-visible
  `claude` conversation — the agent's normal interactive session, seeded
  with the call's prompt as the first message — in its own terminal
  window (Windows: `cmd /c start /wait`), and blocks until that window is
  closed. When `True`, runs headlessly instead (`-p --output-format
  json`, output captured, no window, exits on its own). Every existing
  example transform under `fatass/topology/examples/` passes
  `silent=True` explicitly, since an unattended pipeline run (e.g. a
  `populate.sh`-style batch script) can't wait on a human to close a
  window; a caller using `returns=...` needs `silent=True` for the same
  reason — `free()` reads `.fatass-result.json` back immediately after
  the call returns, so nothing can be waiting on a human to get there.
- **`permission_mode`** (default `"acceptEdits"`, `fatass.core.free.DEFAULT_PERMISSION_MODE`):
  passed straight through as `--permission-mode`. `acceptEdits` is safer
  than the old blanket `bypassPermissions` default — file edits
  (Read/Write/Edit) are auto-accepted so headless runs don't stall
  waiting for approval, but Claude Code's own finer-grained safety checks
  (e.g. on risky Bash commands) still apply rather than being skipped
  outright. Pass `permission_mode="bypassPermissions"` explicitly for a
  call whose prompt genuinely needs unattended shell access.
- **`system_prompt`**: appended (via `--append-system-prompt`, never
  `--system-prompt`, so Claude Code's own baseline system prompt is kept
  rather than replaced) on top of whatever the call already sends. Loaded
  per command from `fatass/prompts/<name>.md` via
  `fatass._internal.prompts.load_system_prompt` — `free.md` backs `fatass
  free`, and `transform.md` backs every `fatass.free()` call made from
  inside a running transform (i.e. what `run`/`apply`/`build` trigger
  indirectly, through whatever transform code they execute — they don't
  call the agent directly themselves). `modify` instead goes through
  `fatass._internal.prompts.load_topology_edit_system_prompt`, which
  prepends `conventions.md` (the static node/transform/`fatass.free()`
  reference — how to declare a dependency, the
  `readable=[...]`/`silent`/`model`/`tools` conventions, etc.) ahead of
  `modify.md`'s own command-specific framing; see why under
  `free_topology` below. A missing prompt file is fine; it just means no
  extra guidance is appended. On top of that, `modify` appends a third,
  class-specific block: `Node.modify_sys_prompt()` is a classmethod
  returning `str | None` (`None` on `Node` itself), called on the
  existing node's real class, imported for this purpose alone
  (best-effort: import failure — e.g. the node's own file being fixed is
  currently broken — just means no extra block, not a command failure).
  `Chain`/`Single`/`Array`/`Repo` override it to teach conventions
  specific to that kind of node (`Single`/`Array` build the text
  per-class off their own `EXT`/`DIM`/`FIELDS`, so it reflects the
  concrete subclass rather than generic placeholder text) only when the
  node being modified is actually one, instead of paying for that
  guidance on every plain-`Node` edit. `create` is fully deterministic
  template scaffolding (`topology_ops/scaffold.py`'s `create_node`/
  `create_transform`) — it never calls the agent, so it has no
  `system_prompt`/`--silent`/`--permission-mode`/`--model` of its own.
- **`model`** (default `None`): passed straight through as `--model` when
  given (an alias like `"opus"`/`"sonnet"`, or a full model name) —
  omitted entirely when `None`, so every existing call keeps using
  whatever the `claude` CLI is already configured/defaulted to. Unlike
  `permission_mode`, this has no fatass-side default of its own.

`modify` and `free` both expose `--silent`, `--permission-mode`, and
`--model` on the CLI; a transform's own `fatass.free(...)` call sets
these as ordinary keyword arguments.

`free_topology` (behind `modify`) grants **no directory besides its own
`cwd`**, with one narrow exception — not the whole topology tree, unlike
an earlier version. On a topology with several populated example
pipelines, passing the whole tree meant every single-function edit paid
to read hundreds of thousands of cache tokens' worth of unrelated nodes
just to infer file conventions by example (see a real run's numbers in
`./log`, `2026-08-25 00:1x`). Those conventions are static now, so they
moved into `conventions.md` (prepended to `modify.md` via
`load_topology_edit_system_prompt`, see above) instead of being taught by
letting the agent browse sibling/dependency nodes it has no real need to
read. The exception: `modify`'s `refine_transform` (only — `refine_node`
has no notion of "dependencies") additionally passes each of the
transform's already-bound dependency nodes' own topology directories as
read-only `add_dirs` (`bound_dep_paths()`, `fatass/topology_ops/bind.py`)
— `cwd` (the transform's own node directory) stays the only writable
one. Lets the agent actually read a dependency's real class shape while
editing a transform that already declares it, without reopening the
"whole tree readable" cost above for every other, unrelated node.

### Logging

Every CLI command dispatch appends one line to `./log` at the repo root
(the command line plus its exit code), via the stdlib `logging` module
(`fatass._internal.logs.get_logger()`, a `FileHandler` configured once per
process — tracked by its own module-level reference rather than "does the
logger have any handlers at all", since something else sharing the same
named logger, e.g. a test runner's own log-capture handler, would
otherwise be mistaken for "already configured" and silently suppress our
FileHandler entirely). `_invoke_claude` additionally logs its `cwd`,
`add_dirs`, `silent`, `permission_mode`, `model`, and the full `prompt`
text before each call, and the resulting exit code after — so every real agent
invocation's exact arguments are recoverable from `./log` afterward. For a
`silent=True` call, it also parses the captured `-p --output-format json`
stdout and logs the `usage` object (token counts) and `total_cost_usd` if
present — best-effort, since that JSON shape is Claude Code's own, not a
contract fatass controls. Token usage isn't available for `silent=False`
(interactive) calls: nothing is captured from a real, inherited terminal.

**Every `run`/`apply`/`build`/`create --prompt`/`modify`/`free` invocation
that reaches `fatass.free()` actually shells out to the real `claude`
CLI — it is a real, billable agent call, not a dry run.** Never run one of
these as a subprocess unless the user actually asked for that specific
call — not to check that a command's arguments parse correctly, not as a
side effect of exploring or testing something else, not "while we're at
it." A `>`-prefixed request or a `>>>`/`>>` line naming the command *is*
that ask; inferring it from context or convenience is not. If you only
need to check parsing, do that separately (e.g. by calling the relevant
`fatass.commands._targets` helpers, or another command's error path)
instead of running the real thing incidentally.

## Message conventions in this project

Messages in this repo may start with one of three prefixes. When they do,
follow the matching rule below instead of your default judgment about how
to respond.

### `>` — natural-language request

A message starting with a single `> ` (e.g. `> create a node named foo`)
is a natural-language request. Translate it into the appropriate
`fatass` command(s) above, then run them through your normal tool-call
flow — so the user sees the standard approval prompt before anything
executes. Don't pre-approve or skip that confirmation for a `>` request.

### `>>>` — literal fatass command

A message starting with `>>> ` is already a fatass CLI invocation, just
missing the `python -m fatass` prefix (e.g. `>>> create foo` means
`python -m fatass create foo`). Prepend it and run it directly — no
confirmation step, and don't stop to ask how to proceed even if it errors;
just report what happened.

### `>>` — raw Python script

One or more consecutive lines starting with `>> ` are a Python script to
run directly with the interpreter, with `fatass` already imported (so
`fatass.topology.my_node...` refers to the already-imported package).
Strip the `>> ` prefix from each line and run the resulting script as-is.

Example — this:
```
>> node = fatass.topology.roster.entry.Entry()
>> print(node._assets_dir())
```
runs as:
```python
import fatass
node = fatass.topology.roster.entry.Entry()
print(node._assets_dir())
```
