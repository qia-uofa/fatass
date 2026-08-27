# fatass

**F**unctional **A**gent for **T**opological **A**sset **S**ystem **S**ynthesization

fatass synthesizes and manages files in a project using the Claude CLI as
an agent. A project is modeled as a graph of **nodes**. Each node has a
Python definition under `fatass/topology/` (a `Node` subclass, named after
the node itself, in `<name>.py`) and an asset directory under `home/` at
the same relative path. Transform files sit directly alongside it in the
same directory — plain Python functions whose `Node`-typed parameters
declare dependencies on other nodes; running a transform invokes a Claude
CLI agent that reads its dependencies' asset directories and writes into
the node's own.

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
- `./log` — one line per CLI command dispatch (command + exit code), plus
  full agent-call details (cwd, flags, prompt, and token usage/cost for
  `--silent` calls) for every `fatass.free()` invocation

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
| `modify <node.path \| transform@node.path> ["..."] [--silent] [--permission-mode M] [--model M]` | Edit an existing node/transform file with an agent; prompt is positional and optional. |
| `move <old.node.path> <new.node.path>` | Move/rename a node, rewriting references to it. |
| `copy <old.node.path> <new.node.path>` | Copy a node, rewriting the copy's internal references to itself. |
| `remove <node.path \| transform@node.path>` | Remove a node (and nested nodes) or a single transform. |
| `bind <transform>@<node.path> <dep.node.path ...>` | Add one or more nodes as declared `Node`-typed dependencies on a transform, without an agent call. |
| `unbind <transform>@<node.path> <dep.node.path ...>` | Remove declared dependencies from a transform, refusing if still referenced in its body. |
| `purge <node.path> [-rs] [-rd] [-rsd]` | Empty a node's own `home/` content; flags reach subnodes/dependencies too. |
| `archive [name] [--node <node.path>]` | Move the whole topology/home trees under `./archive/`, start fresh — or, with `--node`, archive just that node's subtree in place. |
| `retrieve [name] [--node <node.path>]` | Restore an archived topology/home snapshot — or, with `--node` (requires a named archive), just that node back to its original path. |
| `build <node.path> [key=value ...]` | Shorthand for `apply build@<node.path>`. |
| `free <target> ["..."] [--silent] [--permission-mode M] [--model M]` | Ad-hoc agent call scoped to one resolved target directory; prompt is positional and optional. |
| `sh <target> <command...>` | Run a shell command with its cwd resolved from a node, transform, or file target. |
| `cd <expr>` | Change the current node (`FATASS_NODE`) that relative targets resolve against. |
| `pwd` | Print the current node (`FATASS_NODE`). |
| `graph [node.path] [-o/--output ...]` | Write a PlantUML diagram of node inclusion + transform dependencies, rooted at `node.path` (default: whole topology). |
| `ls <node.path \| node.path/rel/path \| transform@node.path>` | List a node's subnodes and transforms (with each transform's input node) — or, for a `/`/`@` target, a raw directory listing like Linux `ls`. |
| `shell` | Interactive REPL — one command per line. |

Node and transform paths are `.`-separated, matching Python module
addressing directly (`node1.node2`, `node1.node2.transforms.synthesize`) —
no separate slash-path translation.

`sh`, `free`, and `ls` share one target grammar: `node1.node2` (that
node's own directory), `transform@node1.node2` (that same node
directory too — a transform file sits directly in it, no separate
subdirectory), or `node1.node2/dir1/dir2/file.txt` (a path relative to the
node's `home/` directory). The node-path portion before the first `/`
must be non-empty — an unquoted `~/rel/path` gets shell-tilde-expanded
into an absolute filesystem path before fatass ever sees it, so a target
starting with `/` is rejected rather than silently resolving against the
current node; write `~.` for an explicit root-relative target. `ls`
treats a bare `node1.node2` specially — listing subnodes/transforms
instead of raw directory content — since that's more useful than a raw
directory listing.

**Every command that reaches `fatass.free()` shells out to the real
`claude` CLI — it's a real, billable agent call, not a dry run.**

See [blueprint/command/README.md](blueprint/command/README.md) for the
full command reference.

### Current node (`FATASS_NODE`)

Every `<node.path>` argument is resolved relative to a **current node**,
stored as `FATASS_NODE` in `.fatass/.env` — `cd` changes it, `pwd` prints
it (no file, or none set, defaults to the topology root). In any
node-path expression:

- A bare path (`node1.node2`) resolves under the current node.
- A leading `~` ignores the current node for an absolute path (`~` alone
  is the root itself).
- A run of *N* consecutive dots ascends *N*-1 levels before descending
  into whatever follows — `.` stays put, `..` goes to the parent,
  `node1..node2` means "node1's parent's child node2".

### `NodeList`

`fatass.NodeList` represents a dynamically-sized, homogeneous sequence
(e.g. "members of a team") without a topology node per item. A single
real node (`class Members(fatass.NodeList): pass`) declares the per-item
schema as its own children; actual items live in `members`'s `home/`
directory as a recursive `.next` chain, grown via `Members.extend()` and
counted via `Members.length()`. `run`/`apply`/`build` accept an indexed
target directly, e.g. `fatass run "members[2].info"` (quote it — other
commands don't understand indexed targets). See
[blueprint/](blueprint/README.md) for the full design.

## Docs

The [blueprint/](blueprint/README.md) directory is fatass's design
documentation — concepts (node, topology, transform, `free()`), directory
layout, caching, and the full command reference. It predates the
implementation and is kept in sync with it as the source of truth for how
the system is meant to work.

`fatass/prompts/conventions.md` is the static node/transform/`free()`
reference handed to every `create`/`modify` agent call as system-prompt
context (ahead of that command's own `create.md`/`modify.md` framing) —
`create`/`modify` grant the agent read access to its own target directory
only, not the rest of the topology, so this file is what teaches it the
project's file conventions instead of letting it infer them by browsing
siblings.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests don't invoke the real `claude` CLI — nothing that shells out to an
agent is exercised end to end; those code paths are tested only through
their error handling (missing directories, bad targets, and the like).
