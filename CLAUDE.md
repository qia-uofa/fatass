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
python -m fatass create <node.path | transform@node.path>[(NodeSubclass)]  # scaffold if missing; e.g. members(NodeList) subclasses fatass.NodeList instead of fatass.Node
python -m fatass create <transform>(<dep.path>[,<dep.path> ...])@<node.path>   # scaffold a transform and bind the given deps onto it in the same call (no agent call for the binding — same as a `bind` right after)
python -m fatass modify <node.path | transform@node.path> "..." [--silent] [--permission-mode M] [--model M]    # edit an existing node/transform file; prompt is positional (empty string becomes the literal text "<empty string>")
python -m fatass move <node.path> <new.node.path>                 # move/rename a node, rewriting references
python -m fatass copy <node.path> <new.node.path>                 # copy a node, rewriting the copy's internal references
python -m fatass remove <node.path | transform@node.path>         # remove a node (and nested nodes) or one transform
python -m fatass purge <node.path> [-rs] [-rd] [-rsd]              # empty a node's home/ content (see command docs for flags)
python -m fatass archive [name] [--node <node.path>]                # move topology/home under ./archive/ and start fresh, or (with --node) archive just that node's subtree in place
python -m fatass retrieve [name] [--node <node.path>]               # restore an archived topology/home snapshot, or (with --node, requires a named archive) just that node back to its original path
python -m fatass build <node.path> [key=value ...]                 # shorthand for `apply build@<node.path>`
python -m fatass free <target> --prompt "..." [--silent] [--permission-mode M] [--model M]  # ad-hoc agent call scoped to a resolved target's directory
python -m fatass sh <target> <command...>                          # run a shell command, cwd resolved from target
python -m fatass cd <expr>                                          # change the current node (FATASS_NODE)
python -m fatass pwd                                                # print the current node (FATASS_NODE)
python -m fatass graph [node.path] [-o/--output ...]                # write a PlantUML diagram of node inclusion + transform dependencies, rooted at node.path (default: whole topology)
python -m fatass ls [-r] <node.path | node.path:rel/path | transform@node.path>  # show a node's own class + subnodes + transforms (each with its dependencies' classes/subnodes), or a raw directory listing for a ':'/'@' target; -r recurses into the full inclusion/directory tree instead of one level
python -m fatass bind [-a/--absolute] <transform>@<node.path> [dep.path ...]    # add nodes as declared Node-typed dependencies on a transform (no agent call); -a replaces the whole dependency set instead of adding to it (unbinds everything first) — with no dep.path at all, -a just clears every existing bind
python -m fatass unbind <transform>@<node.path> <dep.path> [dep.path ...]  # remove nodes from a transform's declared dependencies (no agent call)
python -m fatass vim <node.path | transform@node.path | node.path:rel/path>  # open a node's class file, a transform file, or a home/ file in vim
python -m fatass shell                                              # interactive REPL, one command per line
```

Node/transform paths are `.`-separated, matching Python module addressing
(`node1.node2`, `node1.node2.transforms.synthesize`).

`sh`, `free`, and `ls`'s `:`/`@` targets share one `<target>` grammar
(`fatass.resolve.targets.resolve`): `node1.node2` (that node's own
directory under `fatass/topology/`), `transform@node1.node2` (that same
node directory too — a transform file sits directly in it, no separate
subdirectory), or `node1.node2:dir1/dir2/file.txt` (a path relative to the node's `home/`
assets directory — `node1.node2:./` names that directory itself; a file
path resolves to its parent dir). `ls`'s bare `node1.node2` form (no `:`
or `@`) doesn't resolve through this — it takes the fast path in
`fatass/ls.py:list_node`, which imports the node itself (via
`fatass.core.transform._import_node`) to get its *base* fatass class
(`"Node"` or `"NodeList"` — not its own specific subclass name, which is
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
summaries : NodeList(entry)
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
        summaries : NodeList(
            entry : Node(),
        ),
    ),
)
```

For a `:`/`@` target, `-r` instead walks the real filesystem tree
(`fatass.ls.list_dir_tree`), same trailing-`/`-for-directories convention
as the non-`-r` form, each nesting level indented four spaces further.

`vim` uses the same grammar but through a sibling function,
`fatass.resolve.targets.resolve_file`, which keeps the actual file instead
of collapsing it to its parent directory: `node1.node2` opens that node's
own `<name>.py` class file, `transform@node1.node2` opens that transform's
`.py` file, and `node1.node2:rel/path` opens that path under the node's
`home/` directory (need not already exist — vim creates it on save, same
as `vim newfile.txt` at a shell).

### `NodeList`

`fatass.NodeList` (`fatass/core/node_list.py`) represents a dynamically-
sized, homogeneous sequence without creating a new topology node per
item — the topology stays fully static (still one `<name>.py` per real
node, still discoverable by walking the filesystem before any code
runs). A list can be either **structured** — one real node
(`class Members(fatass.NodeList): pass`) declares the per-item schema as
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
- `members_instance[i]` (`NodeList.__getitem__`) raises
  `TopologyValidationError` naming the current length if `i` is out of
  range — growing only ever happens via an explicit `.extend()`, never as
  a side effect of indexing or reading.
- **Leaf lists:** `members[i]._assets_dir()` (`_NodeListItem._assets_dir()`)
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
  (there's no transform to run there). `sh`/`free`/`create`/`modify`/
  `move`/`remove`/`graph` don't understand indexed targets — only
  `run`/`apply`/`build` do.
- Not supported: a schema child depending on a sibling schema child in
  the same item (e.g. `contribution` reading the same item's `info`) does
  not auto-resolve to the same index — schema-node dependencies should
  point outside their own list.

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
  call the agent directly themselves). `create` and `modify` instead go
  through `fatass._internal.prompts.load_topology_edit_system_prompt`,
  which prepends `conventions.md` (the static node/transform/
  `fatass.free()` reference — how to declare a dependency, the
  `readable=[...]`/`silent`/`model`/`tools` conventions, etc.) ahead of
  `create.md`/`modify.md`'s own command-specific framing; see why under
  `free_topology` below. A missing prompt file is fine; it just means no
  extra guidance is appended. On top of that, `create`/`modify` append a
  third, class-specific block: `Node.create_sys_prompt()`/
  `Node.modify_sys_prompt()` are classmethods returning `str | None`
  (`None` on `Node` itself), called on the node's actual class — for
  `create`, whichever class the `(NodeSubclass)` target suffix names (see
  below); for `modify`, the existing node's real class, imported for this
  purpose alone (best-effort: import failure — e.g. the node's own file
  being fixed is currently broken — just means no extra block, not a
  command failure). `NodeList` overrides both to teach the `.next`-chain
  conventions only when the node being created/modified is actually one,
  instead of paying for that guidance on every plain-`Node` edit.
- **`model`** (default `None`): passed straight through as `--model` when
  given (an alias like `"opus"`/`"sonnet"`, or a full model name) —
  omitted entirely when `None`, so every existing call keeps using
  whatever the `claude` CLI is already configured/defaulted to. Unlike
  `permission_mode`, this has no fatass-side default of its own.

`create`, `modify`, and `free` all expose `--silent`, `--permission-mode`,
and `--model` on the CLI; a transform's own `fatass.free(...)` call sets
these as ordinary keyword arguments.

`free_topology` (behind `create`/`modify`) grants **no directory besides
its own `cwd`**, with one narrow exception — not the whole topology tree,
unlike an earlier version. On a topology with several populated example
pipelines, passing the whole tree meant every single-function edit paid
to read hundreds of thousands of cache tokens' worth of unrelated nodes
just to infer file conventions by example (see a real run's numbers in
`./log`, `2026-08-25 00:1x`). Those conventions are static now, so they
moved into `conventions.md` (prepended to `create.md`/`modify.md` via
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
