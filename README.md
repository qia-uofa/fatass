# fatass

**F**unctional **A**gent for **T**opological **A**sset **S**ystem **S**ynthesization

fatass synthesizes and manages files in a project using the Claude CLI as
an agent. A project is modeled as a graph of **nodes**. Each node has a
Python definition under `fatass/topology/` and an asset directory under
`home/` at the same relative path. A node's `transforms/` submodule holds
plain Python functions whose `Node`-typed parameters declare dependencies
on other nodes; running a transform invokes a Claude CLI agent that reads
its dependencies' asset directories and writes into the node's own.

## Setup

### 1. Prerequisites

- Python 3.10+
- Node.js/npm (only needed to install the `claude` CLI below) or your
  package manager of choice
- `git`, to clone this repo

### 2. Install the Claude CLI

fatass shells out to the real `claude` CLI (Claude Code) for every agent
call, so it has to be installed and authenticated *before* fatass is
useful — `create --prompt`, `run`, `apply`, `build`, `modify`, and `free`
all depend on it.

```bash
npm install -g @anthropic-ai/claude-code
```

See the [Claude Code docs](https://docs.claude.com/en/docs/claude-code)
if you'd rather use the native installer instead of npm.

Then authenticate it once, interactively:

```bash
claude
```

This walks you through logging in (Claude subscription or Anthropic
Console account). If you'd rather use an API key non-interactively —
useful for CI or headless boxes — set `ANTHROPIC_API_KEY` in your
environment instead; the `claude` CLI picks it up automatically and no
login step is needed.

Verify it's on `PATH` and authenticated:

```bash
claude -p "say hi" --output-format json
```

If this fails with a "not found" error, `claude` isn't on `PATH` — fix
that before installing fatass, since every fatass command that reaches
`fatass.free()` will fail the same way (`FreeError: the claude CLI was
not found on PATH`).

### 3. Install fatass

```bash
git clone <this-repo-url>
cd fatass
pip install -e .
```

Editable install, so every run picks up the latest source. This also
installs the `fatass` console script (via `pyproject.toml`'s
`[project.scripts]`), so `fatass ...` works as a shorthand for
`python -m fatass ...` once your `pip`'s script directory is on `PATH`.

For running the test suite too:

```bash
pip install -e ".[dev]"
```

### 4. Layout sanity check

fatass resolves its own paths relative to the installed package (see
`fatass/_paths.py`), not the current working directory, so commands work
from anywhere once installed:

- `fatass/topology/` — node/transform Python definitions
- `home/` — node asset directories (transform inputs/outputs)
- `.fatass/.env` — local state (e.g. `FATASS_NODE`, the `cd`-like current
  node used by `sh`/`free`/`cd` target expressions); safe to delete, and
  already covered by `.gitignore`
- `archive/` — snapshots created by `fatass archive`

No further configuration is required — once `claude` is authenticated
and `fatass` is installed, the [Quickstart](#quickstart) below is a
working example.

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
| `create <node.path \| transform@node.path> [--prompt ""] [--silent] [--permission-mode M] [--model M]` | Scaffold a node or transform if it doesn't exist yet. |
| `modify <node.path \| transform@node.path> --prompt "" [--silent] [--permission-mode M] [--model M]` | Edit an existing node/transform file with an agent. |
| `move <old.node.path> <new.node.path>` | Move/rename a node, rewriting references to it. |
| `copy <old.node.path> <new.node.path>` | Copy a node, rewriting the copy's internal references to itself. |
| `remove <node.path \| transform@node.path>` | Remove a node (and nested nodes) or a single transform. |
| `purge <node.path> [-rs] [-rd] [-rsd]` | Empty a node's own `home/` content; flags reach subnodes/dependencies too. |
| `archive [name] [--node <node.path>]` | Move the whole topology/home trees under `./archive/`, start fresh — or, with `--node`, archive just that node's subtree in place. |
| `retrieve [name] [--node <node.path>]` | Restore an archived topology/home snapshot — or, with `--node` (requires a named archive), just that node back to its original path. |
| `build <node.path> [key=value ...]` | Shorthand for `apply build@<node.path>`. |
| `free <target> --prompt "" [--silent] [--permission-mode M] [--model M]` | Ad-hoc agent call scoped to one resolved target directory. |
| `shell` | Interactive REPL — one command per line. |

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
