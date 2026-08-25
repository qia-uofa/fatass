import fatass
from fatass.topology.examples.writings.seminar.audit.draft import (
    Draft as Draft,
)
from fatass.topology.examples.writings.seminar.audit.issues import (
    Issues as Issues,
)


def build(draft: Draft, issues: Issues):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[draft, issues],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`draft` dependency: the current draft of the essay. Also "
            f"read every file in the readable directory for this node's "
            f"`issues` dependency: the audit findings raised against that "
            f"draft.\n\n"
            f"Resolve every issue by revising the draft accordingly, while "
            f"preserving the draft's original meaning, claims, and evidence "
            f"wherever the issue doesn't require changing them. Leave parts "
            f"of the draft not implicated by any issue unchanged. Do not "
            f"add headings, entry titles, or other scaffolding.\n\n"
            f"Write the result as `draft.md` in the current directory: the "
            f"full essay, with every issue resolved."
        ),
    )
