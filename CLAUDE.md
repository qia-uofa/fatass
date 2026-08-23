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
python -m fatass remove <node.path | transform@node.path>         # remove a node (and nested nodes) or one transform
python -m fatass archive [name]                                    # move topology/nodes under ./archive/, start fresh
python -m fatass retrieve [name]                                   # restore an archived topology/nodes snapshot
python -m fatass build <node.path> [key=value ...]                 # shorthand for `apply build@<node.path>`
python -m fatass free <nodes|topology>.<path> --prompt "..."      # ad-hoc agent call scoped to one directory
```

Node/transform paths are `.`-separated, matching Python module addressing
(`node1.node2`, `node1.node2.transforms.synthesize`).

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
