import fatass


def build():
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[],
        prompt=(
            "Generate two files in the current directory: `app.py` and "
            "`index.html`, for a small local web app that lets an academic "
            "fill out their CV-writing preferences.\n\n"
            "- `app.py` is the server: a minimal, dependency-light HTTP "
            "server (standard library only, e.g. `http.server`) that "
            "serves `index.html`, exposes an endpoint for the page to read "
            "the current preferences state, and an endpoint the page "
            "submits to. On startup and on each read request, the server "
            "reads existing state from `../preferences.json` (one "
            "directory up from `app.py`), if present, so the page shows "
            "the current values. On submit, the server writes the "
            "resulting preferences to `../preferences.json`.\n"
            "- `index.html` is a stylized, multipage survey (plain "
            "HTML/CSS/JS, no build step, no external dependencies) with "
            "pagination and a final review page before submitting.\n\n"
            "Cover these fields:\n"
            "- Target field/discipline.\n"
            "- The CV's purpose: tenure-track job market application, "
            "postdoc application, grant/fellowship application, tenure/"
            "promotion case, or general/all-purpose.\n"
            "- Desired scope: a comprehensive CV with no length limit, vs. "
            "a condensed biosketch-style CV capped at a stated page "
            "count.\n"
            "- Citation style for the publications list (e.g. APA, MLA, "
            "IEEE, or a field-specific numbered style) and whether to bold "
            "the candidate's own name in co-authored entries.\n"
            "- Which sections to include and in what order, from: "
            "Education, Positions/Appointments, Publications, "
            "Presentations and Invited Talks, Grants and Funding, Awards "
            "and Honors, Teaching, Service, Personal Projects, "
            "References.\n"
            "- Whether to split publications into subtypes (journal "
            "articles, conference papers, book chapters, preprints/"
            "working papers) or list them in one combined section.\n"
            "- Whether an \"in preparation\"/\"under review\" subsection "
            "should be included for publications not yet accepted.\n\n"
            "Style: a calm, professional/academic visual theme, applied "
            "consistently across every page."
        ),
    )
