# fatass

fatass synthesizes and manages project files using the Claude CLI as an
agent. A project is a graph of **nodes**: each has a Python definition
under `fatass/topology/` (a `Node` subclass in `node.py`) mirrored by an
asset directory under `home/`. A node's `transforms/` submodule holds
functions whose `Node`-typed parameters declare dependencies on other
nodes; calling one invokes `fatass.free(...)`, which runs the Claude CLI as
a subprocess, reading dependency nodes' directories and writing into the
node's own.

Full design docs: [blueprint/](blueprint/README.md).

## CLI

```
python -m fatass run <node.path>[.transforms.<name>] [--force]   # run transform(s), cache-aware
python -m fatass apply <transform>@<node.path> [key=value ...]    # run one transform with explicit args, ignoring cache
python -m fatass create <node.path | transform@node.path> [--prompt "..."] [--silent] [--permission-mode M] [--model M]  # scaffold if missing
python -m fatass modify <node.path | transform@node.path> --prompt "..." [--silent] [--permission-mode M] [--model M]    # edit an existing node/transform file
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
python -m fatass shell                                              # interactive REPL, one command per line
```

Node/transform paths are `.`-separated, matching Python module addressing
(`node1.node2`, `node1.node2.transforms.synthesize`).

`sh` and `free` share one `<target>` grammar (`fatass.resolve.targets.resolve`):
`node1.node2` (that node's own directory under `fatass/topology/`),
`transform@node1.node2` (that transform file's directory, also under
`fatass/topology/`), or `node1.node2:dir1/dir2/file.txt` (a path relative
to the node's `home/` assets directory — `node1.node2:./` names that
directory itself; a file path resolves to its parent dir).

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
  `fatass._internal.prompts.load_system_prompt` — `create.md`, `modify.md`,
  and `free.md` back the three CLI commands that call the agent directly,
  and `transform.md` backs every `fatass.free()` call made from inside a
  running transform (i.e. what `run`/`apply`/`build` trigger indirectly,
  through whatever transform code they execute — they don't call the
  agent directly themselves). A missing prompt file is fine; it just
  means no extra guidance is appended.
- **`model`** (default `None`): passed straight through as `--model` when
  given (an alias like `"opus"`/`"sonnet"`, or a full model name) —
  omitted entirely when `None`, so every existing call keeps using
  whatever the `claude` CLI is already configured/defaulted to. Unlike
  `permission_mode`, this has no fatass-side default of its own.

`create`, `modify`, and `free` all expose `--silent`, `--permission-mode`,
and `--model` on the CLI; a transform's own `fatass.free(...)` call sets
these as ordinary keyword arguments.

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
>> node = fatass.topology.example_a.Node()
>> print(node._assets_dir())
```
runs as:
```python
import fatass
node = fatass.topology.example_a.Node()
print(node._assets_dir())
```
