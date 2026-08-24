import fatass


def build():
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[],
        prompt=(
            f"Generate two files in the current directory: `app.py` and "
            f"`index.html`, for a small local web app that lets a PhD "
            f"applicant fill out a scouting profile describing what they "
            f"are looking for in a program.\n\n"
            f"- `app.py` is the server: a minimal, dependency-light HTTP "
            f"server (standard library only, e.g. `http.server` or "
            f"`socketserver`) that serves `index.html`, exposes an "
            f"endpoint for the page to read the current profile state, "
            f"and exposes an endpoint the page submits to. On startup and "
            f"on each read request, the server reads the existing profile "
            f"state from `../preferences.json` (i.e. a file named "
            f"`preferences.json` one directory up from `app.py`'s own "
            f"location), if present, so the page can display the current "
            f"values. When the survey is submitted, the server writes the "
            f"resulting profile to `../preferences.json`.\n"
            f"- `index.html` is a stylized, multipage survey (plain HTML/"
            f"CSS/JS, no build step, no external dependencies) with "
            f"pagination between steps (e.g. next/back controls, a "
            f"progress indicator) and a final review page before "
            f"submitting to the server.\n\n"
            f"Cover these fields, grouped into sensible pages:\n"
            f"- Target research areas/subfields and keywords.\n"
            f"- Preferred degree start term.\n"
            f"- Geographic/country preferences and any visa or "
            f"citizenship constraints.\n"
            f"- Funding requirements (fully funded only, vs. "
            f"assistantship/fellowship acceptable).\n"
            f"- Target institution tiers/prestige tolerance.\n"
            f"- Preferred advisor seniority or lab size (junior PI vs. "
            f"established lab).\n"
            f"- Remote vs. onsite fit.\n"
            f"- The application deadline window to prioritize.\n"
            f"- The maximum number of programs/professors to target.\n"
            f"- Desired tone/formality for outreach emails.\n"
            f"- A free-text box for professors, labs, or institutions "
            f"already known to the applicant, so they are not treated as "
            f"new candidates later.\n\n"
            f"Style: a calm, academic visual theme (colors, typography, "
            f"layout), applied consistently across every page."
        ),
    )
