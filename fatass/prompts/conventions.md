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
- Design choice: if a node's `home/` directory is meant to hold exactly
  one file (no ambiguity about which file is "the" content — one PDF, one
  JSON blob, one markdown writeup), name that file `_` with the
  appropriate extension (`_.pdf`, `_.json`, `_.md`, ...) rather than
  inventing a descriptive name — the node's own dotted path already says
  what the file is, so a descriptive filename would only repeat that.
  Reserve a real, descriptive filename for a node whose directory holds
  more than one file (or may grow to).

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

Inside the function body, call `fatass.free(...)` — but only when plain
Python genuinely can't do the job. `free()` invokes a real agent: slower,
costs money, and less predictable than code you can trust. Reach for it
only for a step that needs judgment, generation, or open-ended
reading/searching (write it up, summarize it, rank it, extract
semi-structured facts from prose) — never for anything a few lines of
deterministic Python could do instead (parsing a known file format,
basic string/number manipulation, filesystem bookkeeping, growing a
`Chain`). A transform can freely mix both: plain Python for the
mechanical parts, `free()` only for the part that actually needs an
agent.

```python
fatass.free(
    silent=True,
    permission_mode="acceptEdits",
    model="sonnet",
    effort="medium",
    tools="Read,Write,Edit,Glob,Grep",
    readable=[dep1, dep2],
    prompt="...",
)
```

- `readable` has no default value — it is a required argument on *every*
  `fatass.free(...)` call, even one that grants no dependency read access
  at all. Pass `readable=[]` in that case (e.g. a call whose prompt
  already inlines everything it needs as plain text); never omit the
  keyword.
- `readable` lists every `Node`-typed parameter's instance — this is what
  grants the agent read access to those dependencies' `home/` directories
  when the transform actually *runs*, unrelated to what you (editing this
  file right now) have access to.
- If the transform's output is a file (or files) with a concrete,
  predictable name that *your code* decides — not something the agent
  should choose — don't let the agent write that file itself. Instead set
  `returns=...` (e.g. `returns=str`, `returns=list`, `returns=dict`) so
  the agent reports its result as data, then write it to the named file
  yourself in plain Python right after the `free()` call:

  ```python
  summary = fatass.free(readable=[...], returns=str, silent=True, prompt="...")
  (node._assets_dir() / "summary.md").write_text(summary, encoding="utf-8")
  ```

  Only skip `returns=...` and let the agent write directly into its
  writable directory when the file's name, count, or existence is itself
  part of what the agent is deciding (e.g. it's producing several files
  whose names depend on content it just read or researched).
  **`returns=...` still requires `Write` in `tools`, even though your own
  code writes the final output file** — the agent itself has to write its
  reported result to `.fatass-result.json` before your code ever sees it.
  Never narrow `tools` down to just `"Read,Glob,Grep"` (or similar) on a
  `returns=...` call; that silently breaks the result hand-off instead of
  failing loudly, since the underlying agent may still write *something*
  there under a permissive `permission_mode` — just not reliably.
- `silent=True` is the norm for a transform meant to run unattended as
  part of a batch pipeline (`fatass run`/`apply`/`build`) — that's the
  common case. Only leave the default `silent=False` (an interactive
  session a human watches) for a transform whose real-world consequence
  is high enough to warrant that — e.g. one that prepares outbound
  communication or another hard-to-reverse action.
- `permission_mode`: the default `"acceptEdits"` only auto-approves file
  edits (Read/Write/Edit) — any other tool (`Bash`, `WebSearch`,
  `WebFetch`) still needs an interactive approval prompt. Under
  `silent=True` there's no terminal to answer that prompt, so the call
  doesn't fail — it just hangs forever. **Whenever `silent=True`, also set
  `permission_mode="bypassPermissions"`, unconditionally** — even if
  `tools` is currently just `"Read,Write,Edit,Glob,Grep"` — since a later
  edit adding `Bash`/`WebSearch`/`WebFetch` to `tools` without revisiting
  `permission_mode` would otherwise silently reintroduce the hang.
- Set `model`, `effort`, and `tools` deliberately, least-privilege, based
  on what the prompt you write actually asks the agent to do — don't just
  copy defaults:
  - `tools`: start from `"Read,Write,Edit,Glob,Grep"`. Add `Bash` only if
    the transform reads PDFs (the Read tool alone can misread a PDF as
    password-protected without shell access to fall back on) or needs to
    execute something. Add `WebSearch,WebFetch` only if the prompt sends
    the agent onto the open internet.
  - `model`/`effort`: `model="sonnet"` with the default effort (no
    `effort=` override) is the baseline for most generation/extraction
    work. Reserve `model="opus"` and/or a higher `effort` ("high",
    "xhigh", "max") for a call whose output quality or judgment is the
    actual point of that transform — the real deliverable, a
    ranking/gatekeeping decision, catching a fabricated/inconsistent
    detail — not for routine or purely mechanical steps. Conversely, a
    `free()` call made repeatedly inside a loop (once per item of a list,
    each call individually simple — e.g. one summary per paragraph) should
    use a *cheaper* setup than a one-shot call would: a lower `effort`
    ("low"/"medium") and/or a lighter model, since the cost and latency of
    a heavy setting multiply by every iteration while any one iteration's
    task is usually simpler than a single call doing the whole job at once.
- Write the `prompt` string to name, for each dependency, what its
  readable directory holds and what to do with it — e.g. "profile
  depends on node `examples.phd_application.profile` — read
  `preferences.json` in its readable directory."
- Add a `print(...)` before each meaningful step in the transform's own
  code — starting the transform, before/after each `free()` call, before
  writing an output file, when growing a `Chain`. A `silent=True`
  transform otherwise produces no visible output at all until (or unless)
  it finishes, so a human watching `fatass run`/`apply`/`build` needs
  these to see it's actually making progress.

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
