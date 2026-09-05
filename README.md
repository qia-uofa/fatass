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
useful — `create --prompt`, `run`, `apply`, `build`, `modify`, `debug`,
`init`, and `free` all depend on it.

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
not found at '<path>'`). If `claude` is only reachable from a different
shell/login environment than the one fatass runs in, set
`FATASS_CLAUDE_BIN` in `.fatass/.env` to its full path instead of relying
on `PATH`.

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
`fatass/_internal/paths.py`), not the current working directory, so
commands work from anywhere once installed:

- `fatass/topology/` — node/transform Python definitions. Only the
  `examples` node (and the package's own `__init__.py`) is tracked in
  git by default — every other node is treated as your own
  project/personal data (see `.gitignore`).
- `home/` — node asset directories (transform inputs/outputs); same
  git-ignore convention as `fatass/topology/`, mirrored.
- `.fatass/.env` — local state (`FATASS_NODE`, the `cd`-like current node
  used by most commands' target expressions; `FATASS_CLAUDE_BIN`, an
  explicit override for the `claude` executable's path); safe to delete,
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
| `create <node.path \| transform@node.path>[(NodeSubclass)] [--prompt ""] [--silent] [--permission-mode M] [--model M]` | Scaffold a node or transform if it doesn't exist yet — all-or-nothing: a failure partway never leaves a half-scaffolded node behind. `(NodeSubclass)` subclasses `fatass.<NodeSubclass>` (e.g. `Chain`, `Single`/`Array`/`Tuple` and their typed variants) instead of the default `Node`; see [Node kinds](#node-kinds) below. |
| `modify <node.path \| transform@node.path> ["..."] [--silent] [--permission-mode M] [--model M]` | Edit an existing node/transform file with an agent; prompt is positional and optional. |
| `debug <transform>@<node.path> ["..."] [--silent] [--permission-mode M] [--model M]` | Like `modify`, but framed around root-causing a failing transform — inlines recent `./log` history, shell command history, and shell console output as a scratch file the agent reads (not raw CLI text, to stay well under any OS command-line length limit) alongside read access to the transform's declared dependencies and its own output directory. |
| `move <old.node.path> <new.node.path>` | Move/rename a node, rewriting references to it. All-or-nothing: a failure partway restores the original, and any external files it already rewrote. `<new.node.path>` may end in `.*` (or be bare `*`) to mean "same name, reparented here" (like Unix `mv file dir/`). |
| `copy <old.node.path> <new.node.path>` | Copy a node, rewriting the copy's internal references to itself; same all-or-nothing guarantee and `*` shorthand as `move`. |
| `remove <node.path \| transform@node.path>` | Remove a node (and nested nodes) or a single transform. Refuses if anything outside the removed subtree still depends on it. |
| `bind <transform>@<node.path> <dep.node.path ...>` | Add one or more nodes as declared `Node`-typed dependencies on a transform, without an agent call. Validates every dependency actually exists before writing anything. |
| `unbind <transform>@<node.path> <dep.node.path ...>` | Remove declared dependencies from a transform, refusing if still referenced in its body. |
| `purge <node.path> [-rs] [-rd] [-rsd]` | Empty a node's own `home/` content; flags reach subnodes/dependencies too. |
| `archive [name] [--node <node.path>]` | Move the whole topology/home trees under `./archive/`, start fresh — or, with `--node`, archive just that node's subtree in place. All-or-nothing. |
| `retrieve [name] [--node <node.path>]` | Restore an archived topology/home snapshot — or, with `--node` (requires a named archive), just that node back to its original path. |
| `build <node.path> [key=value ...]` | Shorthand for `apply build@<node.path>`. |
| `init <node.path> [key=value ...]` | Shorthand for `apply init@<node.path>`. |
| `free <target> ["..."] [--silent] [--permission-mode M] [--model M]` | Ad-hoc agent call scoped to one resolved target directory; prompt is positional and optional. |
| `sh <target> <command...>` | Run a shell command with its cwd resolved from a node, transform, or file target. |
| `cd <expr>` | Change the current node (`FATASS_NODE`) that relative targets resolve against. |
| `pwd` | Print the current node (`FATASS_NODE`). |
| `graph [node.path] [-o/--output ...]` | Write a PlantUML diagram of node inclusion + transform dependencies, rooted at `node.path` (default: whole topology). |
| `ls [-r] <node.path \| node.path/rel/path \| transform@node.path>` | List a node's subnodes and transforms (with each transform's input node) — or, for a `/`/`@` target, a raw directory listing like Linux `ls`. `-r` recurses. |
| `len <node.path>` | Print a `Chain`'s current length. |
| `insert <n> <node.path> [path1 path2 ...]` | Insert a `Chain` item at index `n`, shifting the rest back — seeded from the dummy head's template, or from the given files/paths (leaf lists only). |
| `push <node.path>` | If the `Chain` has its own `push` transform, apply it (shorthand for `apply push@<node.path>`); otherwise append one item, seeded as a copy of the dummy head's own content. |
| `pop <node.path> [n]` | Remove a `Chain`'s tail item, or item `n` if given, shifting anything after it forward. Tolerant of Windows read-only files (e.g. a git checkout pushed into an item). |
| `vim <node.path \| transform@node.path \| node.path(rel/path)>` | Open a node's class file, a transform file, or a `home/` file in vim. |
| `shell` | Interactive REPL — one command per line, with history and node-path tab-completion. |

Node and transform paths are `.`-separated, matching Python module
addressing directly (`node1.node2`, `node1.node2.transforms.synthesize`) —
no separate slash-path translation.

`sh`, `free`, `ls`, and `vim` share one target grammar: `node1.node2`
(that node's own directory or class file), `transform@node1.node2` (that
same node directory/file — a transform file sits directly in it, no
separate subdirectory), or `node1.node2(rel/path)` (a path relative to
the node's `home/` directory — `node1.node2()` names the directory
itself). The node-path portion before the first `(` must be non-empty —
an unquoted `~/rel/path` gets shell-tilde-expanded into an absolute
filesystem path before fatass ever sees it, so a target starting with
`(` is rejected rather than silently resolving against the current node;
write `~.` for an explicit root-relative target. `ls`'s bare
`node1.node2` form (no `(`/`@`) is special — it lists subnodes/transforms
instead of raw directory content, since that's more useful than a raw
directory listing.

**Every command that reaches `fatass.free()` shells out to the real
`claude` CLI — it's a real, billable agent call, not a dry run.**

### Current node (`FATASS_NODE`)

Every `<node.path>` argument is resolved relative to a **current node**,
stored as `FATASS_NODE` in `.fatass/.env` — `cd` changes it, `pwd` prints
it (no file, or none set, defaults to the topology root). `shell` keeps
its own in-memory current node for the life of that session, separate
from `.fatass/.env` (so concurrent shells/commands don't step on each
other's `cd`). In any node-path expression:

- A bare path (`node1.node2`) resolves under the current node.
- A leading `~` ignores the current node for an absolute path (`~` alone
  is the root itself).
- A run of *N* consecutive dots ascends *N*-1 levels before descending
  into whatever follows — `.` stays put, `..` goes to the parent,
  `node1..node2` means "node1's parent's child node2".
- A `[N]`/`[*]` Chain index attaches to whatever the walk just landed on,
  rather than becoming its own dotted segment — `.[0]` indexes the
  current node itself, `..[0]` indexes its parent, and `[*]` means "the
  current tail" (`length() - 1`, resolved at call time).

### `Chain`

`fatass.Chain` represents a dynamically-sized, homogeneous sequence
(e.g. "members of a team") without a topology node per item. A single
real node (`class Members(fatass.Chain): pass`) can optionally declare
per-item schema children as its own real subnodes (a *structured* list,
e.g. `members.info`); with none declared, it's a *leaf* list and each
item's content lives in a reserved `.entry` directory instead. Actual
items live in `members`'s `home/` directory as a recursive `.next` chain:

- `Members.extend()` — bare append, just the new `.next` marker (used
  internally by `insert()`; growing this way still correctly
  materializes any `Single`/`Array`/`Tuple` schema child's managed
  file(s) blank on first access, same as a freshly-`create`d node would).
- `Members.insert(index)` (`fatass insert`/`fatass push`, no custom
  `push` transform) — additionally seeds the new item as a copy of the
  dummy head's own template content.
- `Members.length()`, `Members.pop(index=None)` — count / remove
  (default: the tail), shifting the rest to fill the gap, O(1) via
  rename rather than a per-item copy.

`run`/`apply`/`build`/`init` accept an indexed target directly, e.g.
`fatass run "members[2].info"` (quote it — `[`/`]` are shell-glob
characters in some shells); `sh`/`free`/`ls`/`vim` understand an indexed
segment too. Inside a transform on an indexed item's own schema child,
use `fatass.current_node()` to get the correctly depth-scoped class —
a plain module-level `from fatass.topology.<path> import <Class>` import
always resolves to the shared, unindexed dummy head instead, silently
writing every item's output to the same place.

### Node kinds

Besides the default `Node` and `Chain`, a node can subclass one of these
to manage a fixed, deterministic set of files instead of arbitrary
agent-written content — `fatass create <node.path>(<NodeSubclass>)`:

- **`Single`**/`SingleTxt`/`SinglePdf`/`SingleMd`/`SingleJson`/`SingleHtml`/`SingleCsv`
  — exactly one file, named `_` (or `_.<ext>`). `write(content)`
  replaces it, creating it if needed.
- **`Array`**/`ArrayTxt`/`ArrayPdf`/`ArrayMd`/`ArrayJson`/`ArrayHtml`/`ArrayCsv`
  — a fixed-shape grid of files (`DIM = (2, 2, 2)`, set via
  `fatass create grid(ArrayTxt,dim=2x2x2)`), named `_<i>_<j>_...`.
  `write([i, j, ...], content)` writes one.
- **`Tuple`** — a fixed set of *exactly*-named files, one per
  `FIELDS = ("field1", "field2")` (set via
  `fatass create foo(Tuple(field1,field2))`) — no prefix, no extension.
  `write(field, content)` writes one.
- **`Repo`** — a node whose `home/` directory is its own git repository;
  `on_created()` runs `git init` there once, right after scaffolding.

A transform populating any of these must never let `fatass.free(...)`
write into the node's `home/` directory directly — capture the result
(`returns=str`/`dict`) and call `NodeClass.write(...)` yourself instead.

A custom `Node` subclass can hook into fatass's own lifecycle without
touching any command:

- `on_created()` — runs once, right after `fatass create` scaffolds a new
  node of this class (and the topology tree is reloaded so the class is
  actually importable). No-op by default; `Single`/`Array`/`Tuple`/`Repo`
  override it to materialize their managed file(s) immediately.
- `purge_self()` — overrides `fatass purge`'s default (delete everything
  directly under the node's `home/`) with something else, e.g. clearing
  fixed-name files in place instead of removing them. Return `None` (the
  default) to keep the generic behavior.
- `modify_sys_prompt()` — extra system-prompt guidance appended when
  `fatass modify` edits a node/transform of this class, teaching an agent
  editing it whatever convention that kind of node needs followed (this
  is how `Chain`/`Single`/`Array`/`Tuple`/`Repo` teach their own rules).
- `on_child_moved(old_stem, new_stem)` — called on a node's class after
  `fatass move` renames one of its *direct* children in place, so a class
  with its own structure mirroring child names (see `Chain`, which keeps
  every existing `.next` level's mirror directories in sync) can react.

### Safety

Every command that alters the topology (`create`, `move`, `copy`,
`remove`, `bind`/`unbind`, `archive`, `retrieve`) is all-or-nothing: an
exception partway through reverts to the original state instead of
leaving a half-made change on disk — a half-scaffolded node missing its
`__init__.py`, a node moved but not fully renamed, an external reference
rewritten in some files but not others, and so on. Directory deletion
throughout (`pop`, `remove`, archive/retrieve, rollback cleanup) is also
tolerant of Windows' read-only file attribute (set on every file inside a
git checkout's `.git/objects/`, for one) — it clears the attribute and
retries instead of failing outright.

## VSCode extension

`vscode_extension/` is a VSCode extension for browsing and operating on a
fatass topology from inside the editor — activates automatically when a
workspace contains `fatass/topology/`.

- **Topology** view (activity bar): a tree of nodes, dotted-path
  addressed, mirroring `fatass ls -r` — built by walking
  `fatass/topology/` for directories containing a `<name>.py`.
- **Node** view: the selected node's files, toggling (via the swap button
  in the view title) between its `home/` assets and its
  `fatass/topology/` class file directory; supports new file/folder,
  rename, delete, cut/copy/paste, and revealing a file in the OS
  file explorer.
- Right-click a topology node for `cd`, `run`, `build`, `modify`,
  `create`, `move`, `copy`, `remove`, `purge`, `vim` — each shells out to
  `python -m fatass ...` in a shared integrated terminal, so normal
  terminal output/approval applies.

Build it yourself:

```bash
cd vscode_extension
npm install
npm run compile
```

Then run the "Extension" launch config (F5) from a VSCode window opened
on `vscode_extension/`, or `vsce package` for a `.vsix`. See
[vscode_extension/README.md](vscode_extension/README.md) for more.

## Docs

`fatass/prompts/conventions.md` is the static node/transform/`free()`
reference handed to every `create`/`modify`/`debug` agent call as
system-prompt context (ahead of that command's own
`create.md`/`modify.md`/`debug.md` framing) — `create`/`modify` grant the
agent read access to its own target directory only, not the rest of the
topology, so this file is what teaches it the project's file conventions
instead of letting it infer them by browsing siblings.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests don't invoke the real `claude` CLI — nothing that shells out to an
agent is exercised end to end; those code paths are tested only through
their error handling (missing directories, bad targets, and the like).
