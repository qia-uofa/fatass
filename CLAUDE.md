# fatass

fatass synthesizes and manages project files using the Claude CLI as an
agent. A project is a graph of **nodes**: each has a Python definition
under `fatass/topology/` (a `Node` subclass in `node.py`) mirrored by an
asset directory under `nodes/`. A node's `transforms/` submodule holds
functions whose `Node`-typed parameters declare dependencies on other
nodes; calling one invokes `fatass.free(...)`, which runs the Claude CLI as
a subprocess, reading dependency nodes' directories and writing into the
node's own.

Full design docs: [blueprint/](blueprint/README.md).

## CLI

```
python -m fatass run <node.path>[.transforms.<name>] [--force]   # run transform(s), cache-aware
python -m fatass apply <transform>@<node.path> [key=value ...]    # run one transform with explicit args, ignoring cache
python -m fatass create <node.path | transform@node.path> [--prompt "..."]  # scaffold if missing
python -m fatass modify <node.path | transform@node.path> --prompt "..."    # edit an existing node/transform file
python -m fatass move <node.path> <new.node.path>                 # move/rename a node, rewriting references
python -m fatass copy <node.path> <new.node.path>                 # copy a node, rewriting the copy's internal references
python -m fatass remove <node.path | transform@node.path>         # remove a node (and nested nodes) or one transform
python -m fatass purge <node.path> [-rs] [-rd] [-rsd]              # empty a node's nodes/ content (see command docs for flags)
python -m fatass archive [name]                                    # move topology/nodes under ./archive/, start fresh
python -m fatass retrieve [name]                                   # restore an archived topology/nodes snapshot
python -m fatass build <node.path> [key=value ...]                 # shorthand for `apply build@<node.path>`
python -m fatass free <target> --prompt "..."                      # ad-hoc agent call scoped to a resolved target's directory
python -m fatass sh <target> <command...>                          # run a shell command, cwd resolved from target
python -m fatass cd <expr>                                          # change the current node (FATASS_NODE)
python -m fatass pwd                                                # print the current node (FATASS_NODE)
python -m fatass graph [-o/--output ./graph.uml]                    # write a PlantUML diagram of node inclusion + transform dependencies
python -m fatass shell                                              # interactive REPL, one command per line
```

Node/transform paths are `.`-separated, matching Python module addressing
(`node1.node2`, `node1.node2.transforms.synthesize`).

`sh` and `free` share one `<target>` grammar (`fatass.targets.resolve`):
`node1.node2` (that node's own directory under `fatass/topology/`),
`transform@node1.node2` (that transform file's directory, also under
`fatass/topology/`), or `node1.node2:dir1/dir2/file.txt` (a path relative
to the node's `nodes/` assets directory — `node1.node2:./` names that
directory itself; a file path resolves to its parent dir).

### Current node (`FATASS_NODE`)

Every `<node.path>` argument anywhere in the CLI is resolved relative to
a **current node**, stored as `FATASS_NODE` in the dotenv file at
`.fatass/.env` (`fatass.cwd`) — no file, or no `FATASS_NODE` in it,
defaults to `~` (the sentinel for "no current node", i.e. the true
topology root). `cd` changes it, `pwd` prints it. One primitive,
`fatass.cwd.expand`, backs all of it: `fatass.targets.resolve` runs it
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
`_import_tree.reload_all`) — needed because `import fatass` eagerly
imports the whole tree once, and a long-lived process (the `shell` REPL
running several commands in a row) would otherwise keep seeing
`sys.modules` entries from before that command ran.

### `graph`

`fatass.graph.build_graph()` writes a PlantUML (`@startuml`/`@enduml`)
diagram of the whole topology: nested `package` blocks mirror the
inclusion relation (root package is `"topology"`), and one arrow per
transform dependency — `dependency --> owner : transform_name` — draws
the dependency relation, pointing from the dependency into the node
whose transform reads it. A transform with no `Node`-typed dependency
(not reachable via `transform.discover()` today, but handled anyway)
draws from a special `"None"` node instead.

### Logging

Every CLI command dispatch appends one line to `./log` at the repo root
(the command line plus its exit code), via the stdlib `logging` module
(`fatass._logging.get_logger()`, a `FileHandler` configured once per
process). `_invoke_claude` (the single subprocess choke point behind
`free()`, `free_topology()`, and `fatass free`) additionally logs its
`cwd`, `add_dirs`, and the full `prompt` text before each call, and the
resulting exit code after — so every real agent invocation's exact
arguments are recoverable from `./log` afterward.

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
