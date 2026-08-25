import fatass
from fatass.topology.examples.writings.seminar.analysis import Analysis as Analysis


def build(analysis: Analysis):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,Bash",  # Bash: the subject/reference PDFs nested under `analysis` need it, else Read misreads them as password-protected
        readable=[analysis],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`analysis` dependency, including all of its sub nodes: "
            f"`task/` (the seminar assignment/task description and the "
            f"resulting `plan.md`), `subject/` (the subject paper, our "
            f"own sidenote on it, and `analysis.md`), and `references/` "
            f"(each reference paper, its author's sidenote, and the "
            f"corresponding `analysis{{i}}.md`).\n\n"
            f"Plan the final essay's paragraph structure. Follow the "
            f"task's requirements and the plan's proposed structure as "
            f"the backbone, but let the actual content of the subject "
            f"and reference analyses fill in and adjust that structure "
            f"where the material warrants it. The subject paper and our "
            f"own sidenote on it must anchor the largest, most central "
            f"paragraphs; material drawn from the reference analyses "
            f"should appear only where it supports, contrasts with, or "
            f"complicates a point about the subject paper, and never as "
            f"co-equal content.\n\n"
            f"Write a single document, `skeleton.md`, in the current "
            f"directory: one entry per planned paragraph of the essay, "
            f"in order. Each entry is a self-contained prompt that a "
            f"later, separate generation step will use — with no access "
            f"to this planning step's reasoning or to any file besides "
            f"skeleton.md itself — to write that one paragraph. Give "
            f"each entry a working title, then the prompt: state what "
            f"the paragraph must argue or cover, its role relative to "
            f"the paragraphs before and after it, and inline all the "
            f"context that prompt needs to stand alone — the specific "
            f"claims, evidence, and quotes it should draw on (naming "
            f"which of the subject or reference analyses each comes "
            f"from), not just a pointer back to those files. This is a "
            f"set of generation prompts, not prose itself — no full "
            f"paragraphs of the essay, just the instructions and "
            f"context for producing each one.\n\n"
            f"Finally, write `log.md` in the current directory: a short "
            f"record of what you did — every file you read across the "
            f"`task`, `subject`, and `references` sub nodes, and a "
            f"summary of the paragraph prompts you wrote into "
            f"skeleton.md."
        ),
    )
