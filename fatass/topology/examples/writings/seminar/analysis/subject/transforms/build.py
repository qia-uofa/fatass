import fatass
from fatass.topology.examples.writings.seminar.materials.papers.subject import (
    Node as Subject,
)


def build(subject: Subject):
    fatass.free(
        readable=[subject],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`subject` dependency: the original paper (e.g. `paper.pdf`) "
            f"and the sidenotes (e.g. `presentation.md`) — a separate "
            f"author's own analysis, commentary, and experiments run on "
            f"the paper's subject.\n\n"
            f"Write a single analysis document, `analysis.md`, in the "
            f"current directory. Its focus is the sidenote author's "
            f"analysis and experimentation on the paper's subject, read "
            f"in coordination with the original paper — not a summary of "
            f"the paper alone. For each point the sidenotes raise "
            f"(hypothesis, experiment, result, issue, fix, takeaway, "
            f"etc.), tie it back to the specific claim, method, or result "
            f"in the original paper that it responds to, extends, "
            f"tests, or complicates. Where the sidenotes leave a point "
            f"underdeveloped, note what in the paper would resolve or "
            f"further inform it.\n\n"
            f"Structure the document around the sidenote author's "
            f"threads of investigation (one section per distinct "
            f"experiment or line of analysis), rather than mirroring the "
            f"paper's own section structure.\n\n"
            f"Finally, write `log` (no extension) in the current "
            f"directory: a short plain-text record of what you did — the "
            f"files you read from the `subject` dependency, and a summary "
            f"of the threads of investigation you wrote into analysis.md."
        ),
    )
