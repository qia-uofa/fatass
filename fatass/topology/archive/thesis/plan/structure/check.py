import fatass
from fatass.topology.archive.thesis.brainstorm import Brainstorm as Brainstorm
from .structure import Structure


def check(brainstorm: Brainstorm):
    print(
        "Starting check: verifying thesis structure outline covers "
        "everything raised in the brainstorm dialogues"
    )
    report = fatass.free(
        readable=[brainstorm],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="opus",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep",
        prompt="""
brainstorm depends on node `thesis.brainstorm` — read EVERY dialogue log
(timestamped `.md` files, one per brainstorming session) in its readable
directory, not just a sample; each records a free-form conversation about
the thesis and may raise ideas, topics, methods, open questions, or
concerns.

Your own current directory holds the thesis structure outline already
produced from that same brainstorm material, in `_.md` — read it too.

Compare the two: for every idea, topic, method, open question, or concern
raised across ALL the brainstorm dialogues, check whether the outline in
`_.md` addresses it somewhere (a chapter or section that would plausibly
cover it, or an explicit mention).

Produce one Markdown report, brief and skimmable, mostly bullet points
rather than prose:
- Lead with a one-line verdict: fully covered, or gaps found.
- The main list: anything raised in the brainstorm dialogues that the
  outline does NOT clearly address. For each gap, name which
  dialogue/session raised it and a short description of what's missing.
  If nothing is missing, say so explicitly instead of listing anything.
- A short, secondary list (optional): anything in the outline with no
  clear grounding in any brainstorm dialogue (over-scoped or invented
  content), if any.

Keep it tight: bullets over sentences, no filler transitions.

Report the finished report's full Markdown content as your result.
""",
    )
    print("Writing coverage check report to _check.md")
    (Structure()._assets_dir() / "_check.md").write_text(report, encoding="utf-8")
    print("Check complete")
