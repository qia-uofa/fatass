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
- `out/log` — one line per CLI command dispatch (command + exit code), plus
  full agent-call details (cwd, flags, prompt, and token usage/cost for
  `--silent` calls) for every `fatass.free()` invocation; `out/` is also
  where `fatass graph`'s own default `.puml` output goes

No further configuration is required — once `claude` is authenticated
and `fatass` is installed, the [Quickstart](#quickstart) below is a
working example.

## Quickstart

```bash
# scaffold a node, then flesh it out with an agent call
python -m fatass create Spec --prompt "a short spec for a hello-world CLI"

# scaffold a dependent node and a transform on it
python -m fatass create Build
python -m fatass create Build.build --prompt "add a spec: Node parameter, \
  read spec/ and generate source files into the current directory"

# run it — cache-aware, skips if spec/ hasn't changed since the last run
python -m fatass run Build

# run it again, with an explicit non-Node argument, ignoring the cache
python -m fatass apply Build.build style=terse
```

`fatass` is a normal console script after install, so `fatass ...` works
too — `python -m fatass ...` is used above since it needs no `$PATH`
setup.

## Example: `examples.portfolio`

The Quickstart above is a two-node toy; `fatass/topology/examples/portfolio`
is a complete, runnable pipeline instead — tracked in git along with its
own already-populated sample data under `home/examples/portfolio/` — that
turns a person's profile and project data into a built CV and portfolio
site. It's the best single place to see most of fatass's node kinds and
conventions working together in one real project:

```text
examples.portfolio
├── profile/          basic_info (Tuple), photo (SinglePng), summary/
│                     skills/interests (SingleMd), and one Chain per
│                     repeated section (education, working_experience,
│                     research_experience, certifications, languages,
│                     awards, publications) — plus a fetch transform that
│                     extracts all of it from an old CV PDF checkpoint
├── projects/         a Chain of project entries, each with its own info
│                     (Tuple) and summary (SingleMd), init'd from a
│                     sibling source node — see `Projects.Info.init`
├── cv/
│   ├── templates/    a Chain of pushable CV templates (LaTeX + HTML)
│   ├── draft/        build() renders the current template + profile +
│   │                 projects into main.tex/main.pdf/main.html
│   └── checkpoints/  a Chain of saved CV PDF snapshots
├── website/          build() turns the finished CV into a portfolio site
└── main              an interactive transform that reports the
                      portfolio's current state and prompts for what to
                      do next (add a checkpoint, extract info, ...)
```

Try it:

```bash
# report current state, then walk through an interactive menu
python -m fatass apply Examples.Portfolio.main

# or drive pieces individually
python -m fatass run Examples.Portfolio.Cv.Draft
python -m fatass graph Examples.Portfolio
```

`fatass graph` writes a PlantUML diagram of the whole subtree — each node
labeled with its own class name and kind, its transforms listed as members
with their real signatures, and an arrow from every dependency straight to
the specific transform that depends on it (see [`graph`](#commands) below).

## Example: `.sig` files

`examples/*.sig` are standalone signature files — the exact same grammar
[Signatures](#signatures) describes and `fatass ls -r` itself renders,
one whole tree (structure, node kinds, and `{...}` transforms) per file
— for a few more scaffolds, each demonstrating a different corner of it:
`jrpg.sig` (a full game-design pipeline — `Chat` brainstorms feeding
structured `Chain`s of design docs, a `Src<Dir>` tree of generated code,
every transform wired up with its own `#`-comment modify prompt right
above it), `recipe_book.sig` (a `Chain`-of-`Chain` for nested
ingredients), `study_planner.sig` (an `Array` grid), `dependency_audit.sig`
(a `Repo` node), and `discord_bot.sig`. `examples/make.sh` scaffolds
and/or fills one in:

```bash
# structure + every transform as an empty stub, no agent calls
examples/make.sh -t jrpg

# the same, then silently `modify` every transform that has its own
# "#" comment, right after creating it (real agent calls)
examples/make.sh -m jrpg

# both, in order
examples/make.sh -tm jrpg
```

`-t`/`-m`/`-tm` are shorthand for `fatass touch -p examples/<project>.sig`
and `... -m` — see [`touch`](#commands) below.

## Commands

| Command | What it does |
| --- | --- |
| `run <node.path>[.transforms.<name>] [--force]` | Run one or all of a node's transforms, cache-aware. |
| `apply Node.transform [key=value ...]` | Run one transform with explicit args, ignoring cache. |
| `create <node.path[<NodeSubclass ...>] \| PathedNodeSignature.transformName[<params>][(deps)]> [--prompt ""] [--silent] [--permission-mode M] [--model M]` | Scaffold a node or transform if it doesn't exist yet — all-or-nothing: a failure partway never leaves a half-scaffolded node behind. `<NodeSubclass>` subclasses `fatass.<NodeSubclass>` (e.g. `Chain`, `Single`/`Array`/`Tuple` and their typed variants) instead of the default `Node`; see [Node kinds](#node-kinds) below. The transform-target form addresses a transform the way an OOP method call reads — see [Transform targets](#transform-targets) below. |
| `touch <PathedNodeSignature>[<NodeType args>][{transform1<params>(deps);...}][(Child1<Type1>(...),Child2<Type2>)] \| PathedNodeSignature.transformName[<params>][(deps)] \| -p <file> [-m]` | Scaffold one or more nodes (recursively, from a signature string — the exact shape `fatass ls -r` itself renders, transforms included — see [Signatures](#signatures)) and/or transforms (same grammar as `create`'s own transform-target form, or bare inside a node's own `{...}` block). Multiple statements, separated by whitespace and/or commas, are processed independently; every node (from every statement, nested subnodes included) is created in a first pass before any transform is, in a second, so a transform's `(deps)` may reference a node declared anywhere else in the same call, in any order. Each node/transform not already present is created (via `create`, same defaults); an already-existing one (subnodes included) is left alone — safe to re-run after editing/extending a tree. The top-level target's own node.path is PascalCase, same as a transform target's (converted back to snake_case) — a child's is its parent's plus its class name converted the same way (`Topics` -> `.topics`). May span multiple lines for readability, and a `#` starts a comment running to end of line (unless quoted); `-p <file>` reads it from a real file instead of giving it inline. `-m` additionally, silently, `modify`s each transform it just created that has an associated `#` comment — one or more contiguous lines immediately before it, or a single same-line trailing comment after its own `;` (only when that transform's own statement is itself all on one line) — using the comment as the prompt. |
| `modify <node.path \| PathedNodeSignature.transformName[<params>][(deps)]> ["..."] [--silent] [--permission-mode M] [--model M]` | Edit an existing node/transform file with an agent; prompt is positional and optional. The optional `<params>`/`(deps)` verify (not create) that's still the transform's actual signature before modifying it. |
| `debug Node.transform ["..."] [--silent] [--permission-mode M] [--model M]` | Like `modify`, but framed around root-causing a failing transform — inlines recent `out/log` history, shell command history, and shell console output as a scratch file the agent reads (not raw CLI text, to stay well under any OS command-line length limit) alongside read access to the transform's declared dependencies and its own output directory. |
| `move <old.node.path> <target>` | Move/rename a node, rewriting references to it. All-or-nothing: a failure partway restores the original, and any external files it already rewrote. `<target>` (the not-yet-existing destination) may end in `.*` (or be bare `*`) to mean "same name, reparented here" (like Unix `mv file dir/`). |
| `copy <old.node.path> <target>` | Copy a node, rewriting the copy's internal references to itself; same all-or-nothing guarantee and `*` shorthand as `move`. |
| `remove <node.path \| Node.transform>` | Remove a node (and nested nodes) or a single transform. Refuses if anything outside the removed subtree still depends on it. |
| `bind Node.transform <dep.node.path ...>` | Add one or more nodes as declared `Node`-typed dependencies on a transform, without an agent call. Validates every dependency actually exists before writing anything. |
| `unbind Node.transform <dep.node.path ...>` | Remove declared dependencies from a transform, refusing if still referenced in its body. |
| `purge <node.path> [-rs] [-rd] [-rsd]` | Empty a node's own `home/` content; flags reach subnodes/dependencies too. |
| `archive [name] [--node <node.path>]` | Move the whole topology/home trees under `./archive/`, start fresh — or, with `--node`, archive just that node's subtree in place. All-or-nothing. |
| `retrieve [name] [--node <node.path>]` | Restore an archived topology/home snapshot — or, with `--node` (requires a named archive), just that node back to its original path. |
| `build <node.path> [key=value ...]` | Shorthand for `apply Node.build`. |
| `init <node.path> [key=value ...]` | Shorthand for `apply Node.init`. |
| `free <target> ["..."] [--silent] [--permission-mode M] [--model M]` | Ad-hoc agent call scoped to one resolved target directory; prompt is positional and optional. |
| `sh <target> <command...>` | Run a shell command with its cwd resolved from a node, transform, or file target. |
| `cd <expr>` | Change the current node (`FATASS_NODE`) that relative targets resolve against. |
| `pwd` | Print the current node (`FATASS_NODE`). |
| `graph [node.path] [-o/--output ...]` | Write a PlantUML diagram of node inclusion + transform dependencies, rooted at `node.path` (default: whole topology). |
| `ls [-r] <node.path \| node.path/rel/path \| node.path.transformName>` | List a node's subnodes and transforms (with each transform's input node) — or, for a `/`-or-transform target, a raw directory listing like Linux `ls`. `-r` recurses. |
| `chain len <node.path>` | Print a `Chain`'s current length. |
| `chain insert <n> <node.path> [path1 path2 ...]` | Insert a `Chain` item at index `n`, shifting the rest back — seeded from the dummy head's template, or from the given files/paths (leaf lists only). |
| `chain push <node.path>` | If the `Chain` has its own `push` transform, apply it (shorthand for `apply <node.path>.push`); otherwise append one item, seeded as a copy of the dummy head's own content. |
| `chain pop <node.path> [n]` | Remove a `Chain`'s tail item, or item `n` if given, shifting anything after it forward. Tolerant of Windows read-only files (e.g. a git checkout pushed into an item). |
| `dict keys <node.path>` | List a `Dictionary`'s current keys, sorted. |
| `dict set <node.path> <key>` | Create a `Dictionary` key if it doesn't already exist — idempotent (a no-op, leaving existing content alone, if it does) — seeded as a copy of the dummy head's own current content, same idea as `chain push`'s own default. |
| `dict pop <node.path> <key>` | Remove a `Dictionary` key outright. Unlike `chain pop`, nothing else shifts — a key has no position for anything to shift into. |
| `dir path <node.path>` | Print a `Dir` node's resolved real filesystem path — may be chain-indexed (e.g. `Lectures[0].Assets`). |
| `dir set-path <node.path> <real_path>` | Write a `Dir`'s own `.path` file, giving it a real filesystem directory (`PATH` is a computed property, not a class attribute — see `fatass.node.dir`) — independently settable per index if chain-indexed. |
| `dir mirror <node.path>` | Re-run a `Dir`'s `on_created()` — re-scan a root's real directory for subdirectories that appeared since it was first mirrored (its own one-time mirror otherwise never notices them). |
| `vim <node.path \| node.path.transformName \| node.path/rel/path>` | Open a node's class file, a transform file, or a `home/` file in vim. |
| `shell` | Interactive REPL — one command per line, with history and node-path tab-completion. A trailing `<command> >> <path>` redirects that line's own output instead of printing it: `path` containing `/` resolves as a node-path home-dir target (`Node.Path/rel/file`, same grammar as `sh`/`free`/`ls`/`vim`); an absolute filesystem path is used as-is; anything else is a bare relative filename, written under `out/`. Always appends. |

Node and transform paths are `.`-separated, matching Python module
addressing directly (`node1.node2`, `node1.node2.transforms.synthesize`) —
no separate slash-path translation.

Any `<node.path>` argument above that names a node which must already
exist may carry an optional trailing `<NodeType args>` signature
assertion — e.g. `ls "Foo.Bar<Chain>"`, `sh "Foo.Bar<Array dim=2x2>" pwd`
— checked against the node's own real signature (see
[Signatures](#signatures)/[Node kinds](#node-kinds)), raising if it
doesn't match: only the parts you actually write are asserted (a bare
`<Chain>` only checks the kind; `<Array dim=2x2>` checks the kind and
`DIM`). Not supported on `sh`/`free`/`ls`/`vim`'s `node.path/rel/path`
form, nor on an indexed (`Members[2]`/`People[alice]`) target.
`create`'s own `<NodeSubclass ...>` suffix is the same grammar, for the
opposite case — naming a not-yet-existing node's type instead of
asserting an existing one's (`<Dictionary>`/`<Dict>` — the two are
interchangeable — included).

### Transform targets

`create`, `modify`, `apply`, `bind`, `unbind`, `debug`, and `remove`
address a transform the way an OOP method call reads:

```
PathedNodeSignature.transformName<params>(deps)
```

`PathedNodeSignature` is an ordinary node-path expression (the same
"."/".."/"@" relative navigation as everywhere else — see
[Current node](#current-node-fatass_node) below), except every real
name segment is PascalCase, matching that node's own class name
(`Jrpg.Design.Overview`), not its snake_case topology-path segment
(`jrpg.design.overview`) — converted back automatically, the same way
`touch` already converts a child's class name back to its directory
name. `transformName` (the trailing segment after the last `.`) is the
transform's own name, lowerCamelCase (`build`, or a hypothetical
`buildAssets` — converted to the real `build_assets` file/function
name the same way).

`<params>` (space-separated `name:type=value`/`name:type`/`name=value`
entries — the same grammar a node's own named/typed type-args already
use, e.g. `<Chat prompt:str="hi">`) and `(deps)` (comma-separated
`PathedNodeSignature`s, each optionally carrying its own trailing
`<NodeType(args)>` assertion) are both independently omittable, each
defaulting to empty when the other is given but this one isn't:
`Node.transform<params>` alone means `Node.transform<params>()`; a bare
`Node.transform` means no params and no deps at all. A dependency's own
navigation is relative to the transform's OWN target node's PARENT
(not the node itself, and not the real current node) — a dep is
overwhelmingly a sibling of the node it feeds, so that's the bare,
dot-free case — e.g.

```
Jrpg.Design.Overview.build(BrainStorm)
```

means "build Overview from BrainStorm, a sibling of Overview under
Design" — no `..` needed, since deps resolve relative to `Design`
(Overview's own parent) already, regardless of where the command is
actually invoked from. A dep that's instead a CHILD of the transform's
own node (rare) has to repeat the node's own name to get back down to
it, e.g. `Overview.build(Overview.SomeChild)`. `create`/`touch` create the
dependency bindings/plain parameters the same way `bind` would (a
deterministic operation, not an agent call); `modify` instead verifies
`<params>`/`(deps)`, when given, still match the transform's actual
current signature before editing it. `apply`/`bind`/`unbind`/`debug`/
`remove` only ever need the bare `PathedNodeSignature.transformName`
form (no `<params>`/`(deps)` — `apply` takes `key=value` context
arguments separately, `bind`/`unbind` take dep paths as their own
positional arguments).

`sh`, `free`, `ls`, and `vim` share one target grammar: `Node1.Node2`
(that node's own directory or class file), `Node1.Node2.transformName`
(that same node directory/file — a transform file sits directly in it,
no separate subdirectory; the dotted last segment's lowercase leading
letter is what marks it as a transform name rather than a child node,
since every real node-path segment is PascalCase), or
`Node1.Node2/rel/path` (a path relative to the node's `home/` directory
— `Node1.Node2/` names the directory itself). The node-path portion
before the first `/` must be non-empty — a target starting with `/` is
rejected rather than silently resolving against the current node, which
is what an empty node-path expression would otherwise do; write `@/`
for an explicit root-relative target. `ls`'s bare `Node1.Node2` form (no
`/`, no dotted transform) is special — it lists subnodes/transforms
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
- A leading `@` (glued directly onto what follows, no dot — `@Foo`) or
  the equivalent `(@)` (as `ls` itself renders the root's synthetic
  label — needs a `.` before further segments: `(@).Foo`) ignores the
  current node for an absolute path (`@`/`(@)` alone is the root
  itself).
- A run of *N* consecutive dots ascends *N*-1 levels before descending
  into whatever follows — `.` stays put, `..` goes to the parent,
  `node1..node2` means "node1's parent's child node2".
- A `[N]`/`[*]`/`[key]` `Chain`/`Dictionary` index attaches to whatever
  the walk just landed on, rather than becoming its own dotted segment —
  `.[0]` indexes the current node itself, `..[0]` indexes its parent,
  and `[*]` means a `Chain`'s "current tail" (`length() - 1`, resolved
  at call time). Any number of indexed segments may appear along one
  path, nesting one collection inside another, e.g.
  `Courses[eiki].Lecture[0]` (a `Dictionary` entry whose own schema
  child is a `Chain`).

### `Chain` and `Dictionary`

`fatass.Chain` and `fatass.Dictionary` both represent a variable-sized,
homogeneous collection (e.g. "members of a team") without a topology
node per item — `Chain` indexed by position (`[0]`, `[1]`, ..., `[*]`
for the tail), `Dictionary` by an arbitrary string key (`["alice"]`). A
single real node (`class Members(fatass.Chain): pass` /
`class People(fatass.Dictionary): pass`) can optionally declare per-item
schema children as its own real subnodes (a *structured* collection,
e.g. `members.info`); with none declared, it's a *leaf* collection and
each item's content lives in a reserved `.entry` directory instead.
Actual items live in the collection's own `home/` directory:

- `Chain` — a recursive `.next` chain (`members/.next/.next/...`, item
  `i` at depth `i+1`).
- `Dictionary` — a flat `.items/<key>/` directory, one per key. A key is
  a real directory name, literally (no escaping) — so it can't contain
  `\ / . [ ] , : * ? " < > |`, control characters, or leading/trailing
  whitespace (either filesystem-illegal, or structurally significant in
  the `[key]` bracket-target grammar itself).

Both:

- Growing — `Members.extend()` (bare append, just the new `.next`
  marker) or `Members.insert(index)`/`fatass chain push` (no custom
  `push` transform) for a `Chain`; `People.set(key)`/`fatass dict set`
  (`Dictionary`'s own single "add" primitive — no position to insert
  *at*, so no separate extend/insert split) for a `Dictionary`. Except
  for bare `extend()`, all of these seed the new item as a copy of the
  dummy head's own *current* content (its `.entry` and/or declared
  schema-child directories) — the "template" every item structurally
  resembles; growing this way (or via bare `extend()`) still correctly
  materializes any `Single`/`Array`/`Tuple` schema child's managed
  file(s) blank on first access, same as a freshly-`create`d node would.
  `set()` is idempotent — a no-op, leaving existing content alone, if
  `key` already exists.
- Shrinking — `Members.pop(index=None)` (default: the tail), shifting
  the rest to fill the gap, O(1) via rename rather than a per-item copy;
  `People.pop(key)`/`fatass dict pop` instead removes just that one key
  outright — nothing else shifts, since keys have no position for
  anything to shift into.
- `Members.length()` / `People.length()`, `Members.keys()` /
  `People.keys()` (sorted) for counting/listing.

`run`/`apply`/`build`/`init` accept an indexed target directly, e.g.
`fatass run "Members[2].Info"` or `fatass run "People[alice].Info"`
(quote it — `[`/`]` are shell-glob characters in some shells);
`sh`/`free`/`ls`/`vim` understand an indexed segment too — and, nesting
one collection inside another, any number of indexed segments anywhere
along the path, e.g. `Courses[eiki].Lecture[0].Exercise` (a `Dictionary`
entry whose own schema child is a `Chain`). Inside a transform on an
indexed item's own schema child, use `fatass.current_node()` to get the
correctly depth/key-scoped class — a plain module-level `from
fatass.topology.<path> import <Class>` import always resolves to the
shared, unindexed dummy head instead, silently writing every item's
output to the same place.

### Node kinds

Besides the default `Node` and the two variable-sized collections,
`Chain` and `Dictionary` (see above), a node can subclass one of these
to manage a fixed, deterministic set of files instead of arbitrary
agent-written content — `fatass create <node.path><NodeSubclass>`
(`Dictionary` also accepts the shorter alias `<Dict>`, matching `fatass
dict`'s own group name — the two are fully interchangeable, and every
*rendered* signature still always shows the real name, `Dictionary`).
A subclass's own constructor-like arguments go in that same suffix, in
the exact shape `fatass.signature` renders an *existing* node's
signature in — copy a node's own signature (see `fatass ls`, or
[Signatures](#signatures) below) straight into a `create` call to
scaffold another one the same way. One grammar for every argument kind
— space-separated, after the type name:

- A `Tuple`/`Array`'s bare field names (`title role`) and/or (for an
  `Array`) `dim=2x2x2`: `foo<Tuple title role>`, `grid<ArrayTxt
  dim=2x2x2>`.
- A named, typed class attribute (e.g. `Chat`'s `PROMPT`), as a
  `name:type=value` entry, baked into the scaffolded node as an
  annotated attribute (`PROMPT: str = 'hi'`): `my_chat<Chat
  prompt:str=hi>`. Either half is omittable (`name=value` defaults the
  type to `str`; `name:type` defaults the value to `""`).
- `Dir`'s own single path argument: `foo<Dir /abs/path>`.

Quote an entry (double quotes, `\"`/`\\` escapes) if it needs to
contain whitespace itself — a param's value, or a `Dir` path with a
space in it — e.g. `prompt:str="hi, there"`, `foo<Dir "some path">`.
Multiple entries are always space-, never comma-, separated.

- **`Single`**/`SingleTxt`/`SinglePdf`/`SingleMd`/`SingleJson`/`SingleHtml`/`SingleCsv`
  — exactly one file, named `_` (or `_.<ext>`). `write(content)`
  replaces it, creating it if needed.
- **`Array`**/`ArrayTxt`/`ArrayPdf`/`ArrayMd`/`ArrayJson`/`ArrayHtml`/`ArrayCsv`
  — a fixed-shape grid of files (`DIM = (2, 2, 2)`, set via
  `fatass create grid<ArrayTxt dim=2x2x2>`), named `_<i>_<j>_...`.
  `write([i, j, ...], content)` writes one.
- **`Tuple`** — a fixed set of *exactly*-named files, one per
  `FIELDS = ("field1", "field2")` (set via
  `fatass create foo<Tuple field1 field2>`) — no prefix, no extension.
  `write(field, content)` writes one.
- **`Repo`** — a node whose `home/` directory is its own git repository;
  `on_created()` runs `git init` there once, right after scaffolding.
- **`Dir`** — a node whose `home/` (`_assets_dir()`) is a real external
  filesystem directory (`PATH`) instead of the usual `home/<path>`
  location; see `fatass dir path`/`set-path`/`mirror` above, and
  `fatass.node.dir`'s own docstring for the full root/relative/chain-
  indexed design.
- **`Chat`** — manages a real, interactive `claude` CLI session (`fatass
  chat new <node.path><Chat prompt:str=...>`, never a `fatass.free()`
  call — no sandboxing) run with this node's own `home/` as its cwd (so
  anything the session creates there is a tracked artifact) and its own
  `.claude_config/` subdirectory as `CLAUDE_CONFIG_DIR`, so every
  session's transcript/history accumulates there — see
  `fatass.node.chat`'s own docstring.

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
  is how `Chain`/`Dictionary`/`Single`/`Array`/`Tuple`/`Repo` teach their
  own rules).
- `on_child_moved(old_stem, new_stem)` — called on a node's class after
  `fatass move` renames one of its *direct* children in place, so a class
  with its own structure mirroring child names (see `Chain`/`Dictionary`,
  which each keep every existing item's own mirror directories — `.next`
  levels, or `.items/<key>` entries — in sync) can react.

### Signatures

Every node's shape — its real class name, the fatass kind it's built on,
that kind's own constructor-like arguments, its own transforms, and its
subnode tree — has one formal text grammar, `fatass.signature`, used
everywhere a node's shape is either *shown* (`ls`, `ls -r`, `graph`,
error messages naming a node's actual kind) or *specified* (`create`'s
`<NodeSubclass ...>` suffix, `touch`'s whole input):

```
NodeClassName<NodeType argument1 argument2>{transform1<params>(deps);transform2<params>(deps);}(SubNodeSignature1,SubNodeSignature2,...)
```

- `NodeClassName` — the node's own real Python class name (PascalCase,
  e.g. `Lectures`), never its snake_case topology-path segment.
- `<NodeType argument1 argument2>` — the fatass kind it's built on
  (`Node`/`Chain`/`Dictionary`/`Single`/`Array`/`Tuple`/`Repo`/`Dir`/
  `Chat`, or a typed variant) plus that kind's own arguments — see
  [Node kinds](#node-kinds) for the argument grammar itself.
- `{...}` — the node's own transforms, each
  `transformName<params>(deps)`, `;`-terminated (including the last
  one — a deliberate "statement list" convention, unlike the
  comma-separated groups elsewhere, so appending an entry by hand never
  touches the one before it) — see
  [Transform targets](#transform-targets) for what `<params>`/`(deps)`
  mean; a dep here is always spelled relative to the transform's own
  node's PARENT, exactly like everywhere else, never as an absolute
  path.
- `(...)` — its direct subnodes, each recursively the same grammar.

Every piece past the bare class name is independently omittable, and
each omission has an implied default that only matters for *input*
(`create`/`touch`, scaffolding a node that doesn't exist yet): an
omitted type defaults to plain `Node()`, omitted transforms/subnodes
default to none declared. Rendering an *existing* node never fabricates
a default back in — an omitted piece is simply not printed, so a node's
own rendered signature (e.g. from `ls`) is always valid input to
recreate it (or one shaped like it) via `create`/`touch`.

#### Presets

Two independent axes control how much of a shown node's shape gets
printed — a **typing degree** for the node itself:

| Degree | Shown as |
| --- | --- |
| 1 (none) | `NodeClassName` |
| 2 (simple) | `NodeClassName<NodeType>` |
| 3 (full) | `NodeClassName<NodeType arg1 arg2>` |

— and a **structure degree** for its subnodes:

| Degree | Subnodes shown as |
| --- | --- |
| 4 (simple) | `(Child1,Child2)` — one level, each child at typing degree 1, not recursed |
| 5 (full) | `(Child1<...>,Child2<...>)` — every child at the SAME typing degree as this node, recursed all the way down |

(There's no bare structure degree — a node with no `(...)` at all is
just whatever its typing-degree-alone signature already is.) The two
degrees can also differ between a node and its descendants (e.g. "full
typing for this node, simple typing recursed underneath") — see
`fatass.signature.mixed_full_structured`.

Named presets (`fatass.signature.PRESETS`, and each importable directly,
e.g. `from fatass.signature import FULL_SIGNATURE`):

| Preset | Degrees | Renders as |
| --- | --- | --- |
| `BASE` | 1 | `NodeClassName` |
| `SIMPLE_TYPED` | 2 | `NodeClassName<NodeType>` |
| `FULL_TYPED` | 3 | `NodeClassName<NodeType arg1 arg2>` |
| `SIMPLE_STRUCTURED` | 1x4 | `NodeClassName(Child1,Child2)` |
| `FULL_STRUCTURED` | 1x5 | `NodeClassName(Child1(...),Child2(...))` — untyped all the way down |
| `SIMPLE_TYPED_SIMPLE_STRUCTURED` | 2x4 | `NodeClassName<NodeType>(Child1,Child2)` |
| `FULL_TYPED_SIMPLE_STRUCTURED` | 3x4 | `NodeClassName<NodeType args>(Child1,Child2)` |
| `SIMPLE_TYPED_FULL_STRUCTURED` | 2x5 | `NodeClassName<NodeType>(...)` — same degree-2 typing recursed |
| `FULL_TYPED_FULL_STRUCTURED` | 3x5 | `NodeClassName<NodeType args>(...)` — same degree-3 typing recursed; "everything, everywhere" |
| `FULL_SIGNATURE` | 3x5 + transforms | `FULL_TYPED_FULL_STRUCTURED` plus each node's own `{...}` transforms block, propagated to every descendant |

— plus every asymmetric "this node at one typing degree, every
descendant at a *different* one" combination, named
`<self>_typed_based_<descendant>_typed_full_structured` (e.g.
`simple_typed_based_full_typed_full_structured`).

`fatass ls -r` uses `FULL_SIGNATURE`, pretty-printed (one child/transform
per line, indented by nesting depth — the same layout a hand-written
`.sig` file already uses, e.g. `examples/jrpg.sig`) — copy its output
straight into `touch`/`touch -p <file>` to recreate the same tree,
transforms included, elsewhere. `fatass ls` (non-recursive) shows one
node's own degree-2x4-plus-transforms view, dense (one line).

#### Pathed vs. bare

Every preset above names a node by its bare class name — fine for a node
shown *in its own local subtree* (a subnode, or the node the signature
is rooted at), ambiguous for one that can live anywhere else in the
topology (a transform dependency, or a target `ls`/`graph` names
directly). `pathed_signature(node_path, config)` — what `ls`/`graph`
use for exactly that case — instead identifies a node by its absolute
topology path (`@Foo.Bar`, or `(@)` for the true root). A transform's
own deps inside a `{...}` block are handled differently again: always
spelled *relative to the transform's own node's parent* (never
absolute, and regardless of the caller's own pathed/bare choice for the
rest of the signature) — the same shortest dot-navigation form
[Current node](#current-node-fatass_node) describes, e.g. `..Design.Overview`
rather than the fully-qualified `@Jrpg.Design.Overview` — so the exact
text `ls`/`FULL_SIGNATURE` renders for a transform's own deps is always
valid `touch` input that recreates the same binding.

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
  file explorer. A `Chain`/`Dictionary` node's own items show as
  `Name[i]`/`Name[key]` rows alongside its regular content, never the
  raw `.next`/`.items` directories — expanding one shows that item's own
  schema-child directories plus, unwrapped, its `.entry` content.
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
