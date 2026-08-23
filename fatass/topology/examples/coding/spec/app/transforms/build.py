import fatass
from fatass.topology.examples.coding.spec import Node as Spec


def build(spec: Spec, prompt: str = "a python project"):
    fatass.free(
        readable=[spec],
        prompt=(
            f"Generate two files in the current directory: `app.py` and "
            f"`index.html`, for a small local web app that lets a user "
            f"interactively customize a spec document for the following "
            f"kind of project: {prompt!r}.\n\n"
            f"- `app.py` is the server: a minimal, dependency-light HTTP "
            f"server (standard library only, e.g. `http.server` or "
            f"`socketserver`) that serves `index.html`, exposes an "
            f"endpoint for the page to read the current spec state, and "
            f"exposes an endpoint the page submits to. On startup and on "
            f"each read request, the server reads the existing spec state "
            f"from `../spec.json` (i.e. a file named `spec.json` one "
            f"directory up from `app.py`'s own location), if present, so "
            f"the page can display the current state. When the survey is "
            f"submitted, the server writes the resulting spec document to "
            f"`../spec.json`.\n"
            f"- `index.html` is a stylized, multipage survey (plain HTML/CSS/"
            f"JS, no build step, no external dependencies) that walks the "
            f"user through customizing the spec document's content — "
            f"sections, requirements, constraints, etc. relevant to "
            f"{prompt!r} — with pagination between steps (e.g. next/back "
            f"controls, a progress indicator), and a final review page "
            f"before submitting to the server.\n\n"
            f"Style: pick a visual theme (colors, typography, layout) that "
            f"fits {prompt!r} rather than a generic default, and apply it "
            f"consistently across every page of the survey.\n"
            f"Content: derive the specific sections, questions, and fields "
            f"of the survey from {prompt!r} — cover the aspects a spec "
            f"document for that kind of project would actually need "
            f"(e.g. goals, scope, constraints, key components), rather "
            f"than a generic one-size-fits-all questionnaire.\n\n"
            f"Look at the readable directory for this node's parent (an "
            f"existing spec document or conventions, if any) and match its "
            f"structure and tone where applicable."
        ),
    )
