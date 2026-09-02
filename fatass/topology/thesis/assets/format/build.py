import fatass
from fatass.topology.thesis.assets.format import Format as Format
from fatass.topology.thesis.brainstorm import Brainstorm as Brainstorm


def build(brainstorm: Brainstorm):
    node = Format()

    print("profiling the thesis writer from brainstorm logs")
    profile = fatass.free(
        readable=[brainstorm],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep",
        prompt=(
            "brainstorm depends on node `thesis.brainstorm` — its readable "
            "directory holds one or more timestamped free-form brainstorming "
            "conversation logs between the thesis writer and an agent "
            "(filenames like `YYYYMMDD-HHMMSS.md`, each with '## User' and "
            "'## Agent' sections). Read all of them in full. From what the "
            "writer says across these conversations — their research "
            "interests, academic background, working style, personality, "
            "concerns, and how they talk about their own thesis — write a "
            "profile of the thesis writer: who they are, their voice, their "
            "priorities, and anything that should inform how their thesis is "
            "formatted and written. Return the full markdown text of the "
            "profile, nothing else."
        ),
    )
    print("writing _profile.md")
    (node._assets_dir() / "_profile.md").write_text(profile, encoding="utf-8")

    print("researching format/style examples and drafting guides")
    guides = fatass.free(
        readable=[],
        returns=dict,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        prompt=(
            "Read `_profile.md` in your own working directory — a profile of "
            "this thesis's writer, just produced from their brainstorming "
            "conversations. This is a Bachelorarbeit (bachelor's thesis) at "
            "the Fachbereich Informatik, Goethe-Universität Frankfurt, "
            "supervised by Prof. Dr. Visvanathan Ramesh (Systems Engineering "
            "for Vision and Cognition). Using the web search and fetch "
            "tools, search for that department's and university's actual, "
            "current official requirements for a Bachelorarbeit's format — "
            "e.g. the Fachbereich Informatik / Prüfungsamt Informatik "
            "guidelines or Prüfungsordnung, and the examination office's "
            "submission requirements (page/word limits, required sections "
            "like the Eidesstattliche Erklärung/declaration of authorship, "
            "language, margins, binding, citation style if mandated, "
            "electronic submission format, etc.). Then produce two separate "
            "documents:\n"
            "- a format guide, organized around a clear hard/soft split: "
            "**hard requirements** are the ones the department/university "
            "actually mandates — cite where each one comes from (which "
            "document/page) and flag anything you could not verify from an "
            "official source as unconfirmed rather than presenting it as a "
            "hard requirement; **soft requirements** are conventions that "
            "are recommended, customary in the field, or drawn from the "
            "supervisor's group's own practice but not formally mandated. "
            "Keep the two clearly separated so the writer can tell what is "
            "non-negotiable from what is a suggestion;\n"
            "- a style guide: writing-style conventions for the thesis — "
            "voice, tone, terminology, sentence and paragraph conventions, "
            "and how the writer's own voice (from the profile) should come "
            "through while still fitting the field's norms.\n"
            "Return a JSON object with exactly two keys, 'format' and "
            "'style', each holding the full markdown text of that document. "
            "Do not write either file yourself."
        ),
    )
    print("writing _format.md and _style.md")
    (node._assets_dir() / "_format.md").write_text(guides["format"], encoding="utf-8")
    (node._assets_dir() / "_style.md").write_text(guides["style"], encoding="utf-8")
