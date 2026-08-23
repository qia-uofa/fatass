# fatass

**F**unctional **A**gent for **T**opological **A**sset **S**ystem **S**ynthesization

fatass synthesizes and manages files in a project using the Claude CLI as
an agent. A project is modeled as a graph of **nodes**. Each node has a
Python definition under `fatass/topology/` and an asset directory under
`nodes/` at the same relative path. A node's `transforms/` submodule holds
plain Python functions whose `Node`-typed parameters declare dependencies
on other nodes; running a transform invokes a Claude CLI agent that reads
its dependencies' asset directories and writes into the node's own.

## Install

```bash
pip install -e .
```

Editable install, so every run picks up the latest source. The `claude`
CLI must be on `PATH` for anything that actually invokes an agent.

## Quickstart

```bash
# scaffold a node, then flesh it out with an agent call
python -m fatass create spec --prompt "a short spec for a hello-world CLI"

# scaffold a dependent node and a transform on it
python -m fatass create build
python -m fatass create build@build --prompt "add a spec: Node parameter, \
  read spec/ and generate source files into the current directory"

# run it — cache-aware, skips if spec/ hasn't changed since the last run
python -m fatass run build

# run it again, with an explicit non-Node argument, ignoring the cache
python -m fatass apply build@build style=terse
```

`fatass` is a normal console script after install, so `fatass ...` works
too — `python -m fatass ...` is used above since it needs no `$PATH`
setup.

## Commands

| Command | What it does |
| --- | --- |
| `run <node.path>[.transforms.<name>] [--force]` | Run one or all of a node's transforms, cache-aware. |
| `apply <transform>@<node.path> [key=value ...]` | Run one transform with explicit args, ignoring cache. |
| `create <node.path \| transform@node.path> [--prompt ""]` | Scaffold a node or transform if it doesn't exist yet. |
| `modify <node.path \| transform@node.path> --prompt ""` | Edit an existing node/transform file with an agent. |
| `move <old.node.path> <new.node.path>` | Move/rename a node, rewriting references to it. |
| `remove <node.path \| transform@node.path>` | Remove a node (and nested nodes) or a single transform. |
| `archive [name]` | Move the whole topology/nodes trees under `./archive/`, start fresh. |
| `retrieve [name]` | Restore an archived topology/nodes snapshot. |
| `build <node.path> [key=value ...]` | Shorthand for `apply build@<node.path>`. |
| `free <nodes\|topology>.<path> --prompt ""` | Ad-hoc agent call scoped to one directory. |

Node and transform paths are `.`-separated, matching Python module
addressing directly (`node1.node2`, `node1.node2.transforms.synthesize`) —
no separate slash-path translation.

**Every command that reaches `fatass.free()` shells out to the real
`claude` CLI — it's a real, billable agent call, not a dry run.**

See [blueprint/command/README.md](blueprint/command/README.md) for the
full command reference.

## Docs

The [blueprint/](blueprint/README.md) directory is fatass's design
documentation — concepts (node, topology, transform, `free()`), directory
layout, caching, and the full command reference. It predates the
implementation and is kept in sync with it as the source of truth for how
the system is meant to work.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests don't invoke the real `claude` CLI — nothing that shells out to an
agent is exercised end to end; those code paths are tested only through
their error handling (missing directories, bad targets, and the like).
