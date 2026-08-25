import fatass
from fatass.topology.examples.writings.seminar.materials.papers import (
    Papers as Papers,
)


def build(papers: Papers):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,Bash",  # Bash: reading the reference PDFs needs it, else Read misreads them as password-protected
        readable=[papers],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`papers` dependency. `subject/` holds our subject paper "
            f"(e.g. `paper.pdf`) and our own sidenote on it (e.g. "
            f"`presentation.md`). `references/` holds one or more "
            f"reference papers (e.g. `paper1.pdf`, `paper2.pdf`, ...), "
            f"each accompanied by another student's own "
            f"sidenote/presentation on that paper (e.g. "
            f"`presentation1.md`, `presentation2.md`, ...).\n\n"
            f"For each reference paper i, write a single analysis "
            f"document, `analysis{{i}}.md`, in the current directory. Its "
            f"focus is that other student's sidenotes/presentation on "
            f"their reference paper — read in coordination with the "
            f"reference paper itself — and how their points of analysis "
            f"connect to our subject paper and our own sidenote on it. "
            f"For each point the reference student's sidenotes raise "
            f"(hypothesis, experiment, result, issue, fix, takeaway, "
            f"etc.), tie it back to: (a) the specific claim, method, or "
            f"result in their reference paper that it responds to, "
            f"extends, tests, or complicates, and (b) any claim, method, "
            f"or result in our subject paper or our own sidenote that it "
            f"echoes, contradicts, extends, or otherwise bears on. Where "
            f"a reference student's point has no clear bearing on our "
            f"subject paper, say so briefly rather than forcing a "
            f"connection.\n\n"
            f"Structure each document around the reference student's own "
            f"threads of investigation (one section per distinct "
            f"experiment or line of analysis), rather than mirroring "
            f"either paper's own section structure.\n\n"
            f"Finally, write `log.md` in the current directory: a short "
            f"record of what you did — the reference papers and sidenotes "
            f"you read, which `analysis{{i}}.md` corresponds to which "
            f"reference paper, and a summary of the connections you drew "
            f"back to our subject paper and sidenote."
        ),
    )
