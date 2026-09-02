import fatass
from fatass.topology.thesis.assets import Assets as Assets
from fatass.topology.thesis.citations import Citations as Citations
from fatass.topology.thesis.examples import Examples as Examples
from fatass.topology.thesis.experiment import Experiment as Experiment
from fatass.topology.thesis.plan import Plan as Plan


def build(
    assets: Assets,
    citations: Citations,
    examples: Examples,
    experiment: Experiment,
    plan: Plan,
):
    print("build: starting thesis draft composition")
    fatass.free(
        readable=[assets, citations, examples, experiment, plan],
        silent=False,
        permission_mode="bypassPermissions",
        model="opus",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,Bash,WebSearch,WebFetch",
        prompt="""
Write a full draft of this thesis as a set of per-section Markdown files —
never as one long document.

- Dependencies, and what to do with each:
  - `plan` (node `thesis.plan`) — read `structure/_.md` in its readable
    directory: the chapter-by-chapter outline already agreed for this
    thesis (chapters, their sections, and which experiment/module or
    brainstorm material feeds each). Use it as the backbone: write the
    document as exactly this chapter/section structure, adapting only if
    something in it is clearly stale against what you find in the other
    dependencies below.
  - `experiment` (node `thesis.experiment`) — its readable directory
    nests everything about the underlying work:
    - `docs/paper/` — the main paper this thesis builds on. Read it in
      full (it may be a PDF; if the Read tool misreads it as
      password-protected or garbled, fall back to Bash to extract its
      text) and understand its theory, method, and claims before writing
      anything that depends on them.
    - `code/` — the original, complete implementation of that paper.
      Read enough of it to know what the paper's method actually does in
      practice.
    - `code_morph/` — the student's own expansion/adaptation of that
      implementation, which is the actual scope of this thesis's
      contribution. Read the whole codebase, not a sample, and
      understand precisely what it changes, adds, or narrows relative to
      `code/`.
    - `code_morph/`'s notebooks (wherever they sit inside it) — each
      notebook is one experiment the student actually ran. Read every
      notebook's code, markdown commentary, and cell outputs in full;
      this is your primary source for what experiments exist, what each
      one measures, and what it found.
    - You may execute non-notebook code under `code/` or `code_morph/`
      (e.g. running a script, a REPL snippet) if doing so helps you
      understand what it does. Never execute or re-run the notebooks
      themselves, though — rely solely on each notebook's already-saved
      cell outputs for results.
  - `assets` (node `thesis.assets`) — its readable directory nests:
    - `data/` — the raw data, results, and figures produced by running
      the notebooks above. Treat this as the only authoritative source
      for any number, table, or figure you put in the thesis — never
      invent a result that isn't backed by a file in here. Where a
      figure is relevant to a point you're making, embed it with a
      Markdown image reference using its path inside this directory,
      with a caption.
    - `format/` — read `_format.md` (required format: hard vs. soft
      requirements), `_style.md` (writing-style conventions), and
      `_profile.md` (the writer's own voice/profile). The document you
      write must satisfy every hard requirement in `_format.md` and
      follow `_style.md` and `_profile.md` throughout.
    - `equations/` — read `_.md`: the thesis's already-assembled,
      cross-consistent collection of equations. Reuse these equations
      verbatim (don't derive your own competing notation) at a
      *moderate* rate — only where an equation genuinely carries the
      point (a definition, a lemma, a key derivation), never as
      decoration or for routine steps prose already covers.
  - `citations` (node `thesis.citations`) — read whatever bibliography
    or reference material already exists in its readable directory and
    cite from it where it fits. That alone is not enough, though: as you
    write, whenever a claim needs support (background/related-work
    claims, comparisons to prior methods, terminology, related results),
    use the web search and fetch tools to find an actual, real, citable
    source for it and cite that too. Never fabricate a citation. Cite
    consistently in whatever style `format/_format.md` or
    `format/_style.md` specifies; if neither specifies one, pick one
    standard academic style and use it uniformly throughout.
  - `examples` (node `thesis.examples`) — its readable directory holds
    past theses gathered as reference material. Read them for structure,
    tone, section conventions, and how they integrate
    citations/equations/figures — as models for form, not as content or
    claims to copy.

- Quality standards to hold every figure, data point, parameter, and
  result to throughout:
  - Every figure you embed must be accompanied by prose explaining it —
    what it shows, how to read its axes/legend, and what point it makes
    — never just dropped in with a bare caption.
  - Every reported data point or measurement must come with error
    analysis — variance, confidence intervals, error bars, or another
    concrete treatment of uncertainty, drawn from what's actually
    available in `assets/data/` or the notebooks' own outputs. Don't
    state a number as if it were exact when the underlying data carries
    variability.
  - Every parameter choice (hyperparameters, thresholds, model/config
    choices) must be justified — explain why that value or setting was
    chosen, citing the paper, the code, or the experiment notebooks as
    the basis, not just listed.
  - Every result must be both interpreted (what it means, in the context
    of the thesis's claims) and connected to its implementation (how it
    was produced — which experiment, code path, or method actually
    generated it) — never reported as a bare number or claim on its own.
  - Never reproduce concrete source code (no literal code blocks or
    snippets lifted from `code/` or `code_morph/`). When a method's
    procedure needs to be shown precisely, express it as pseudocode
    instead. Otherwise, narrate methodology and experiments the way a
    scientist writes up their own work in prose: what was set up, what
    was run, what was observed, rather than walking through the
    implementation function by function.

- If anything in this prompt conflicts with another file, prompt, or
  description you read while working (`plan`, `format/_format.md`,
  `format/_style.md`, `format/_profile.md`, the example theses, or
  anything else), this prompt wins. Follow this prompt's instructions
  over the conflicting one.

- Most important of all: avoid writing patterns that read as
  AI-generated. No em dashes. No "this is not X, this is Y" or
  "it's not just X, it's Y" constructions. No other stock AI phrasing or
  rhythm. Write the way a scientist writes a thesis: plain, direct
  sentences, first-person-plural or passive voice as fits the section,
  and don't lean on jargon where a simpler word says the same thing.

- Output format — one file per section, written directly into your own
  current working directory (this node's own writable directory):
  - Name each file `<index>-<name>.md`, where `<index>` is a
    zero-padded two-digit number giving that section's position in
    `plan`'s outline (`01`, `02`, `03`, ...) and `<name>` is a short
    kebab-case slug of that section's title (e.g.
    `01-introduction.md`, `02-related-work.md`). Use one file per
    top-level chapter in the plan, unless the plan's outline is itself
    structured at a finer per-section granularity, in which case match
    that granularity instead.
  - Before writing anything, check this directory for `<index>-<name>.md`
    files already present from a prior run. If any exist, read every one
    of them in full to see exactly what has already been drafted.
    Continue from there: never rewrite, duplicate, or restart a section
    that already has a file — resume by writing only the remaining
    sections, in the plan's order, picking up the index count where the
    existing files leave off.
  - Before writing the first section's file, check this directory for a
    manifest file named `sections.md`.
    - If it doesn't exist yet (a fresh run), create it now, before any
      section file. List every section from `plan`'s outline, in order:
      its index, its filename (`<index>-<name>.md`), its title, and a
      target length for it (a word or page count). Derive each section's
      target length from `plan`'s outline together with the format
      node's length requirements (`assets/format/_format.md`) —
      apportion the thesis's total required length across sections by
      their relative scope/weight in the plan, not evenly.
    - If it already exists (a resumed run), read it instead of
      regenerating it — it carries the section plan and lengths already
      agreed in a prior run. Only update it if something about the
      already-drafted sections makes an already-recorded length
      obsolete.
    - While drafting each section, always revisit `sections.md`'s
      recorded target length for that section and keep the section's
      actual length close to it — don't let a section overshoot its
      budgeted length. If a section's content genuinely needs a
      different length than planned, update that section's entry in
      `sections.md` to match, rather than silently drifting from it.
  - Write the complete thesis now, section by section per `plan`'s
    outline (skipping any section already drafted, per above), grounded
    throughout in the paper, the original and morphed code, the actual
    experiment results in `assets/data/`, the required format/style, and
    real citations. Write each finished section's file yourself as you
    go — don't hold the whole thesis in memory and dump it at the end.
""",
    )
    print("build: done")
