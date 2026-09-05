import fatass
from fatass.topology.archive.thesis.brainstorm import Brainstorm as Brainstorm
from fatass.topology.archive.thesis.experiment.code_morph import CodeMorph as CodeMorph
from .structure import Structure


def build(brainstorm: Brainstorm, code_morph: CodeMorph):
    print(
        "Starting build: documenting bachelor thesis structure from "
        "brainstorm dialogues and code_morph codebase"
    )
    outline = fatass.free(
        readable=[brainstorm, code_morph],
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
the thesis.

code_morph depends on node `thesis.experiment.code_morph` — read the
entire codebase in its readable directory (the `vconf/` Python package
implementing the experiments: activation steering, patching, noising,
representation swapping, ground truth, metrics, sentiment scoring,
models, data, and pipeline code, plus any experiment logs or notes sitting
alongside it, and any notebooks present).

Using both — the ideas, motivations, and open questions raised across ALL
of the brainstorm dialogues, and the actual experiments/methods
implemented across the WHOLE codebase — lay out the structure of a
bachelor thesis on this work.

Produce one Markdown document that is brief and skimmable, mostly bullet
points rather than prose:
- A chapter-by-chapter outline (e.g. Introduction, Related Work,
  Background/Method, Experiments, Results, Discussion, Conclusion — adapt
  the names and count to what this specific project actually needs;
  don't force a generic template that doesn't fit).
- Under each chapter, a bullet list of the sections it should contain,
  each as a short fragment (not a full paragraph) naming what content
  goes there — grounded in the specific experiments, findings, and ideas
  found in the codebase and dialogues, not generic filler.
- Where relevant, tack on which experiment/module (e.g. `exp1_steering.py`,
  `exp2_patching.py`, ...) or which brainstorm conversation feeds which
  section, so the mapping from existing work to thesis structure is
  explicit — as a short parenthetical or sub-bullet, not more prose.

Keep the whole document tight: bullets over sentences, no filler
transitions, no restating the same point twice.

Report the finished document's full Markdown content as your result.
""",
    )
    print("Writing thesis structure outline to _.md")
    (Structure()._assets_dir() / "_.md").write_text(outline, encoding="utf-8")
    print("Build complete")
