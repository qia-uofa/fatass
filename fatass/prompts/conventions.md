You are editing a file under `fatass/topology/` in a project that models
itself as a graph of nodes. You do **not** have read access to the rest
of the topology tree — only to the file(s) in your current directory.
Everything you need to know about the project's conventions is below;
don't assume you can browse sibling or dependency nodes to learn them by
example, and don't guess at another node's actual file layout or content.

## Nodes

Each node is a Python package under `fatass/topology/<dotted.path>/`:
- `<lastsegment>.py` (its own directory's own name, e.g. `roster/roster.py`)
  defines `class <PascalCase>(fatass.Node): pass` — the class name is
  PascalCase of the node's own directory name (e.g. `writing_sample` ->
  `WritingSample`) — almost always exactly this boilerplate, unless the
  instruction you were given specifically asks you to customize it.
- `__init__.py` re-exports it: `from .<lastsegment> import <PascalCase>`.
- A node's own assets (generated output, or hand-populated input) live in
  a mirrored directory under `home/<dotted.path>/` — prompts refer to
  this as that node's "readable directory" or "home/" directory. You are
  not writing into that directory here.

## Transforms

Transform files sit directly in the node's own directory — one file per
transform (e.g. `build.py` defines `def build(...):` — the function name
always matches the file's stem), alongside the node's own `<lastsegment>.py`
and `__init__.py`, no separate subdirectory. Every node conventionally has
a `build` transform; other names are valid too when asked for.

A transform function's parameters work two ways:
- A parameter type-hinted with a `Node` subclass declares a dependency on
  that node. Import it as:
  `from fatass.topology.<full.dotted.path.from.root> import <Alias> as <Alias>`
  The path is always the *full* dotted path from the topology root (e.g.
  `fatass.topology.examples.phd_application.profile`), never relative to
  the file you're editing. `<Alias>` is the dependency's own real class
  name — PascalCase of its last path segment (`profile` -> `Profile`,
  `writing_sample` -> `WritingSample`, `hunt.shortlist` -> `Shortlist`) —
  and doubles as the conventional local parameter alias, since that's
  literally the name `__init__.py` exports it under. Keep the `as <Alias>`
  even though it repeats the name: it's a no-op in the common case, and a
  real disambiguator if two different dependencies' last path segments
  happen to coincide.
- Any other parameter (a plain type like `str`, optionally with a
  default) is a context argument, not a dependency — e.g.
  `def build(spec: Spec, side_note: str = ""):`.
- A transform with no `Node`-typed parameter at all is valid — it
  declares no dependencies (e.g. a node that scaffolds a generic app from
  scratch, with nothing upstream to read).

Inside the function body, call `fatass.free(...)` to actually do the
work:

```python
fatass.free(
    silent=True,
    model="sonnet",
    tools="Read,Write,Edit,Glob,Grep",
    readable=[dep1, dep2],
    prompt="...",
)
```

- `readable` lists every `Node`-typed parameter's instance — this is what
  grants the agent read access to those dependencies' `home/` directories
  when the transform actually *runs*, unrelated to what you (editing this
  file right now) have access to.
- `silent=True` is the norm for a transform meant to run unattended as
  part of a batch pipeline (`fatass run`/`apply`/`build`) — that's the
  common case. Only leave the default `silent=False` (an interactive
  session a human watches) for a transform whose real-world consequence
  is high enough to warrant that — e.g. one that prepares outbound
  communication or another hard-to-reverse action.
- Set `model`, `tools`, and `permission_mode` deliberately, least-
  privilege, based on what the prompt you write actually asks the agent
  to do — don't just copy defaults:
  - `tools`: start from `"Read,Write,Edit,Glob,Grep"`. Add `Bash` only if
    the transform reads PDFs (the Read tool alone can misread a PDF as
    password-protected without shell access to fall back on) or needs to
    execute something. Add `WebSearch,WebFetch` only if the prompt sends
    the agent onto the open internet.
  - `model`: `"sonnet"` is the default-quality choice for most
    generation/extraction work. Reserve `"opus"` for a call whose output
    quality or judgment is the actual point of that transform — the real
    deliverable, a ranking/gatekeeping decision, or catching a
    fabricated/inconsistent detail — not for routine or purely mechanical
    steps.
- Write the `prompt` string to name, for each dependency, what its
  readable directory holds and what to do with it — e.g. "profile
  depends on node `examples.phd_application.profile` — read
  `preferences.json` in its readable directory."

## `bind`/`unbind` — the deterministic way to wire a dependency

If the only thing an instruction asks for is adding or removing a
`Node`-typed dependency — no other change to the file — prefer telling
the user to run `fatass bind <transform>@<node.path> <dep.path>` (or
`unbind`) instead of doing it yourself here. Those commands edit the
signature and import mechanically, without an agent call, and are
idempotent/safe (bind skips an already-bound dependency; unbind refuses
if the parameter is still referenced in the body). They don't touch a
`fatass.free(readable=[...])` call or the prompt text, so once a
dependency is bound this way, you (or a later `modify` call) still need
to actually wire it into a `free()` call's `readable=[...]` and explain
its purpose in the prompt for it to do anything at runtime.
