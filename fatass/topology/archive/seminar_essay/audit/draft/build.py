import fatass
from fatass.topology.archive.seminar_essay.drafting.annotation import (
    Annotation as Annotation,
)
from fatass.topology.archive.seminar_essay.drafting.draft import (
    Draft as Draft,
)


def build(draft: Draft, annotation: Annotation):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[draft, annotation],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`draft` dependency: the current draft of the essay. Also "
            f"read every file in the readable directory for this node's "
            f"`annotation` dependency: `annotation.md`, which flags "
            f"specific lines, sentences, sentence pairs, or groups in the "
            f"draft that read as AI-patterned, naming which pattern(s) "
            f"each flagged unit matches and why.\n\n"
            f"Rewrite the flagged units to remove the noted AI patterns, "
            f"while preserving each unit's original meaning, claims, and "
            f"evidence exactly. Leave every unflagged part of the draft "
            f"unchanged. Do not add headings, entry titles, or other "
            f"scaffolding.\n\n"
            f"Write the result as `draft.md` in the current directory: "
            f"the full essay, with the flagged units revised and "
            f"everything else carried over verbatim."
        ),
    )
