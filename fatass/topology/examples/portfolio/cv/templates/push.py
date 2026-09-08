import dataclasses
import shutil
import subprocess

import fatass
from fatass.topology.examples.portfolio.cv.templates import Templates as Templates

_STAGING = ".push-staging"
_GENERATOR = "build_cv.py"


@dataclasses.dataclass
class _TemplateMeta:
    name: str
    description: str


def _read_field(node, field: str) -> str:
    """Tuple nodes only expose write()/_file_path(), not a read() of
    their own (see draft/build.py's _TupleView for why) — read the
    backing file directly, defensively (it may not exist yet)."""
    path = node._file_path(field)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def push(prompt: str, templates: Templates, name: str = "", description: str = ""):
    print("push: reading existing template names to avoid a collision")
    existing_names = [
        n for i in range(Templates.length())
        if (n := _read_field(Templates()[i].info, "name"))
    ]

    print("push: extending templates chain with a new item")
    Templates.extend()
    index = Templates.length() - 1
    item = Templates()[index]

    staging_dir = Templates._assets_dir() / _STAGING
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    if name:
        name_instruction = f"- name: use exactly {name!r} (already decided) — write it back unchanged.\n"
    else:
        name_instruction = (
            "- name: invent a short, distinctive name (2-4 words, Title "
            "Case, no punctuation) fitting this template's style. It MUST "
            "NOT collide with, or be a trivial variant of, any of these "
            f"existing template names: {existing_names!r}. If your first "
            "idea collides, pick a different one.\n"
        )
    if description:
        description_instruction = f"- description: use exactly {description!r} (already decided) — write it back unchanged.\n"
    else:
        description_instruction = (
            "- description: write one plain sentence summarizing the "
            "template's look/style, for someone browsing a list of "
            "templates.\n"
        )

    print(f"push: generating tex-source generator script for templates[{index}] via free()")
    meta = fatass.free(
        readable=[],
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        returns=_TemplateMeta,
        prompt=(
            "Write a single self-contained Python script implementing a CV "
            f"template, based on this description:\n\n"
            f"{prompt}\n\n"
            f"Write it as `{_STAGING}/{_GENERATOR}` (create the directory if "
            "it doesn't already exist). The deliverable is a Python script "
            "that WRITES a LaTeX source file — not a LaTeX project itself.\n\n"
            "Contract for the script:\n"
            "- It defines a function `generate_tex(profile, projects) -> "
            "str` that returns the full contents of a `main.tex` file "
            "rendering a CV from `profile` (a `Profile` node instance) and "
            "`projects` (a `Project` chain instance — an indexable, sized "
            "list of project items).\n"
            "- The script must NOT import `Profile`, `Project`, or `scope` "
            "itself — assume all three names are already available in its "
            "namespace by the time `generate_tex` actually runs in "
            "production (those imports are added elsewhere, later, when "
            "this script is wired into the real pipeline).\n"
            "- `scope` is a string, one of `'all'`, `'present'`, or "
            "`'auto'`, and `generate_tex` must read it (as a global, or "
            "take it as a third parameter `generate_tex(profile, "
            "projects, scope)` — either is fine as long as it's actually "
            "consulted) to decide which data goes into the rendered CV:\n"
            "  - `scope == 'all'`: every Chain item from `profile` and "
            "`projects` must appear in the output, even a sparse one with "
            "only one or two fields filled in — items are never dropped "
            "for being incomplete.\n"
            "  - `scope == 'present'`: include only fields and Chain "
            "items that actually have data; a missing field or an "
            "entirely empty section is simply left out of the document.\n"
            "  - `scope == 'auto'`: select whichever data is useful for "
            "the CV this template is going for (this may end up being "
            "everything) — same as `'all'` but scoped to a sensible "
            "subset rather than forcing literally everything in.\n"
            "  - NEVER emit a placeholder (e.g. '[NAME]', '[DATE]', "
            "'[COMPANY]') for a missing/empty field, under ANY scope, "
            "including `'all'`. A CV with visible bracketed filler text "
            "reads as broken, not as a helpful prompt to fill something "
            "in. Instead, when a field is missing, adapt the surrounding "
            "layout so its absence isn't visible as a gap or stray "
            "punctuation: e.g. if a date range's end is missing, print "
            "just the start (not 'Sep 2022 -- [END]'); if a job's "
            "location is missing, drop that segment and its separator "
            "entirely rather than leaving 'Role, ,  (dates)'; if every "
            "field in an entry is missing, drop that entry/line instead "
            "of rendering an all-placeholder block. Every joiner (\", "
            "\".join(...), \" | \".join(...), an f-string with several "
            "optional segments) should filter out empty/None pieces "
            "before joining, so the punctuation around a gap disappears "
            "along with the gap itself.\n\n"
            "- `profile`'s real shape (a fatass topology node) is:\n"
            "  - `profile.basic_info` is a Tuple with fields `name`, "
            "`email`, `phone`, `location`, `website`, `linkedin`, `github` "
            "— read one via `profile.basic_info.read('name')`.\n"
            "  - `profile.summary`, `profile.skills`, `profile.interests` "
            "are SingleMd — read the full markdown text via "
            "`profile.summary.read()` (no field name).\n"
            "  - `profile.photo` is a profile photo (binary image, not "
            "text) — it has NO `.read()`; get its file path via "
            "`profile.photo.path()`, which returns a string path if a "
            "real, non-empty photo exists, or `None` if there isn't one "
            "yet. When a path is returned, embed it with `\\includegraphics` "
            "(the script must `\\usepackage{graphicx}`) — e.g. small and "
            "right-aligned next to the name/contact block, using a "
            "`minipage` split rather than nesting a table inside another "
            "table. Read this OUTSIDE of `collect_all()`/`restyle()` "
            "entirely — a filesystem path is not text `free()` should "
            "ever be asked to rewrite, and its presence must never gate "
            "on `scope` the way a text field's presence does — no "
            "photo should never render a placeholder box.\n"
            "  - `profile.courseworks` is a SingleCsv with a single "
            "column `course` — read it via `profile.courseworks.read()`, "
            "which returns the rows (treat each row defensively — it may "
            "come back as a string, a dict with key `course`, or an "
            "object with a `.course`/`.read('course')` accessor; write a "
            "small helper that tries all three and falls back to "
            "`str(row)`).\n"
            "  - `profile.education`, `profile.working_experience`, "
            "`profile.research_experience`, `profile.publications`, "
            "`profile.awards`, `profile.certifications`, "
            "`profile.languages` are each a Chain — get its length via "
            "`profile.<name>.length()`, index it via `profile.<name>[i]`, "
            "then read that item's declared schema child `entry` (e.g. "
            "`profile.education[i].entry.read('institution')`). Their "
            "`entry` Tuple fields are: education = `institution, degree, "
            "field_of_study, start_time, end_time, location, honors`; "
            "working_experience = `company, role, location, start_time, "
            "end_time, description`; research_experience = `lab, advisor, "
            "institution, role, start_time, end_time, description`; "
            "publications = `title, venue, date, authors, url`; awards = "
            "`title, issuer, date, description`; certifications = `name, "
            "issuer, date, credential_id, detail`; languages = `language, "
            "proficiency`.\n"
            "- `projects` itself is a Chain — get its length via "
            "`projects.length()` and index it via `projects[i]`, which "
            "exposes three schema children: `projects[i].info` (a Tuple "
            "with fields `titile` (note: misspelled exactly this way in "
            "the real schema — use `titile`, not `title`), `role`, "
            "`start_time`, `end_time`, `context`, `url` (a project link, "
            "e.g. a repo or live demo — render it as a hyperlink next to "
            "the title when present, empty string if not), read via "
            "`.info.read('titile')` etc.), `projects[i].summary` (a "
            "SingleMd, read via `.summary.read()`), and `projects[i]."
            "source` (an arbitrary node holding the project's own source "
            "material — not needed for rendering the CV listing itself, "
            "safe to ignore).\n"
            "- Wrap every `.read(...)` call in a small defensive helper "
            "that catches any exception (missing/empty backing file, "
            "etc.) and returns a default instead of raising, since real "
            "data will often be incomplete.\n"
            "- For any field that's missing/empty/None, substitute a clear "
            "placeholder in the rendered LaTeX (e.g. '[NAME]', '[EMAIL]') "
            "rather than raising or leaving a blank hole in the layout — "
            "essential fields (name, at least one section) always get a "
            "placeholder so the CV still renders as a complete document. "
            "A Chain with zero items (e.g. no publications) should simply "
            "omit that section rather than showing a placeholder for it.\n"
            "- Escape all user-provided text for LaTeX special characters "
            "(&, %, $, #, _, {, }, ~, ^, \\\\).\n"
            "- The raw field values are filled in by a human over time, "
            "directly into plain text files, with NO enforced format — "
            "the same logical field routinely shows up in wildly "
            "different shapes (e.g. a date written as '20251001' in one "
            "entry, '04/2023' in another, and '27 June 2026' in a third; "
            "multiple emails or phone numbers dumped into one field "
            "separated only by a raw newline, with no delimiter at all "
            "once whitespace is collapsed; a project summary that's the "
            "entire original markdown file, unbounded in length; a "
            "sub-detail like a certification's score left blank while "
            "the certification itself is real). Never assume a field is "
            "already in a renderable shape — always normalize it before "
            "rendering.\n"
            "- Do this normalization with ONE batched agent call per "
            "build, rather than shipping raw field values straight into "
            "the LaTeX, or hand-writing regex/string-munging to guess at "
            "every possible human-entered format yourself. Implement it "
            "as: (1) a `collect_all(profile, projects)`-style function "
            "that walks the exact same `.read(...)`/`.length()`/`[i]` "
            "calls described above and gathers every stylable raw value, "
            "completely unmodified, into one flat, JSON-serializable "
            "dict (same shape you'd otherwise read field-by-field while "
            "rendering); (2) `from fatass.core.free import free, "
            "current_node`, guarded by `try/except ImportError: free = "
            "None; current_node = None` so the module still imports "
            "standalone (e.g. under `python " + _GENERATOR + "`); (3) a "
            "`restyle(raw)` helper that returns `raw` unchanged if `free "
            "is None`, otherwise calls `free([], <prompt>, returns=dict, "
            "silent=True)` exactly once for the whole document, wrapped "
            "in a broad `try/except Exception` that falls back to the raw "
            "dict (and prints a warning to stderr) if the call fails — a "
            "broken agent invocation must never fail the whole build. "
            "`silent=True` is required — without it `free()` opens a "
            "live, human-visible terminal window and blocks on it, which "
            "is wrong for a call that's meant to run unattended inside a "
            "build.\n"
            "- CRITICAL: never embed the raw JSON dict inline in that "
            "`<prompt>` string (e.g. via `f\"...{json.dumps(raw)}\"` or "
            "string concatenation). A real CV's raw data (unbounded "
            "project summaries, long descriptions) routinely runs to "
            "tens of thousands of characters — `free()`'s silent mode "
            "passes the prompt as a literal `-p` command-line argument, "
            "and Windows' `CreateProcess` hard-caps a command line at "
            "~32,767 characters, so an inlined payload WILL eventually "
            "exceed it, making `restyle()` fail immediately (WinError "
            "206) and silently fall back to unstyled raw data every "
            "single time, no matter how good the wording is. Instead: "
            "write `json.dumps(raw, ensure_ascii=False, indent=2)` to a "
            "small file (e.g. `.restyle-raw.json`) inside "
            "`Path(current_node()._assets_dir())` if `current_node` is "
            "available else `Path('.')`, delete it in a `finally` block, "
            "and have the prompt itself just say to read that filename "
            "in the current directory — keeping the actual `-p` argument "
            "short regardless of how much raw CV data there is.\n"
            "- The `<prompt>` passed to that one `free()` call MUST spell "
            "out an explicit, field-by-field normalization contract — a "
            "target format to convert TO, not just \"clean this up\" — "
            "covering at least:\n"
            "  - any `*_time`/`date`-named field: whatever format it "
            "arrives in (an 8-digit 'YYYYMMDD' string, 'MM/YYYY', "
            "'DD Month YYYY', 'Month YYYY', a bare year, or empty), "
            "output a single consistent 'Mon YYYY' style (e.g. "
            "'Oct 2025'); keep 'Present' and empty strings exactly as-is; "
            "if only a year is recoverable, output just the year.\n"
            "  - any field that may hold more than one value entered by "
            "a human (email, phone, and similarly-shaped contact "
            "fields): split on whatever the human actually used as a "
            "separator (newlines, commas, semicolons, slashes, or just "
            "whitespace runs between two recognizable values), dedupe, "
            "and rejoin with one single consistent separator string "
            "(e.g. ' | ') — never leave two values glued together with "
            "no separator between them.\n"
            "  - long free-text fields (profile summary, any per-entry "
            "`description`/`detail`, a project's summary): these arrive "
            "as unbounded, as-authored prose or a raw markdown dump with "
            "no length limit — compress each down to a fixed target "
            "(e.g. profile summary to at most ~3 sentences / ~60 words; "
            "a per-entry description or project summary to at most ~40 "
            "words) by keeping the most salient facts (role, scale, "
            "outcome) and dropping the rest — actually rewrite/condense "
            "the content, don't just hard-truncate the string mid-"
            "sentence.\n"
            "  - list-like fields (courseworks, languages, a skills list): "
            "dedupe, apply consistent capitalization, and rejoin as a "
            "clean, consistently-delimited list — same rule as any other "
            "field: whatever separator the human actually used, "
            "normalize it to one single consistent separator on output.\n"
            "- A long flat list (courseworks is the typical case — often "
            "20+ short items) must be laid out as an actual LaTeX table "
            "(e.g. `tabularx` with 2-3 columns, filling row-major, adding "
            "the package to the preamble) rather than one long "
            "comma-separated run-on paragraph — it reads far better and "
            "avoids one giant unbroken line.\n"
            "  - a field that is genuinely empty in the raw data (e.g. a "
            "missing certification score/detail) MUST be returned as an "
            "empty string, exactly as given — restyle() only reformats "
            "values that exist, it must never invent, guess, or fabricate "
            "content for a field that has none; deciding whether an "
            "empty field gets a placeholder or is omitted entirely is "
            "the renderer's job (via `scope`), not restyle()'s.\n"
            "  - restyle() must return the exact same JSON shape it was "
            "given — same keys, same nesting, same list length and "
            "order for every Chain/list field — it only ever rewrites "
            "values in place, never adds, removes, merges, or reorders "
            "entries.\n"
            "- Have `generate_tex` call `collect_all` then `restyle` "
            "first, and have every section-rendering function read from "
            "the restyled dict instead of calling `.read(...)` on the "
            "node objects directly. This only works because `generate_tex` "
            "runs inside a real fatass transform (an owning node is set "
            "in context), so don't worry about wiring that context up "
            "yourself.\n"
            "- Under `if __name__ == '__main__':`, define made-up mock "
            "`Profile` and `Project`-chain objects that expose exactly "
            "the same interface described above (`.read(field)` on "
            "Tuples, `.read()` on SingleMd/SingleCsv, `.length()` + "
            "`[i]` on Chains, with schema children named `entry`/`info`/"
            "`summary`/`source`), populated with plausible made-up CV "
            "content (a name, contact info, a few education/work entries, "
            "skills, and 2-3 example projects with titles, roles, dates, "
            "and descriptions), plus a mock `scope = 'auto'`. Call "
            "`generate_tex` with them, write the result to `main.tex` "
            "next to the script, and then run `pdflatex "
            "-interaction=nonstopmode -halt-on-error main.tex` (via "
            "subprocess, twice, for references) in that same directory, "
            f"so that running the script directly (`python {_GENERATOR}`) "
            "produces both `main.tex` and a compiled `main.pdf` as a "
            "demonstration of the template.\n"
            "- Also define `generate_html(data, scope, photo_path=None) -> "
            "str`, rendering the SAME content in the SAME visual language "
            "(same accent color, same section order, same entry layout — "
            "bold title, colored date, italic subtitle) as an actual "
            ".html document (inline `<style>`, no external CSS/JS), and "
            "write its result to `main.html` next to `main.tex`. Reuse "
            "the already-collected/already-restyled `data` (and "
            "`photo_path`) that `generate_tex` computed — never call "
            "`collect_all`/`restyle` a second time just to get a second "
            "output format; `restyle()` is one real, slow agent call, and "
            "doubling it per build for no reason is wasteful. If a real "
            "photo exists, copy its file next to `main.html` (an "
            "`<img src=...>` needs a real sibling file, not the original "
            "absolute path) and reference it by its own filename. Writing "
            "`main.html` must be a best-effort side effect wrapped in its "
            "own `try/except` — a failure there must never break the "
            "actual PDF build.\n"
            "- Include any supporting .cls/.sty/asset files the layout "
            f"needs, written into `{_STAGING}/` alongside the script.\n\n"
            "After writing the script, run it standalone "
            f"(`cd {_STAGING} && python {_GENERATOR}`) to confirm it "
            "produces both a `main.pdf` and a `main.html` with no errors, "
            "using the made-up example data.\n\n"
            "Finally, on top of writing the script, also come up with:\n"
            + name_instruction
            + description_instruction
        ),
    )

    print(f"push: writing info for templates[{index}]")
    item.info.write("name", name or meta.name)
    item.info.write("description", description or meta.description)

    source_dir = item.source._assets_dir()
    for child in staging_dir.iterdir():
        target = source_dir / child.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        shutil.move(str(child), str(target))
    shutil.rmtree(staging_dir, ignore_errors=True)

    main_tex = source_dir / "main.tex"
    if main_tex.exists():
        print(f"push: building templates[{index}]'s texproject (pdflatex main.tex)")
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                cwd=source_dir,
                check=True,
            )
    else:
        print(f"push: no main.tex found in templates[{index}]'s source — skipping build")
