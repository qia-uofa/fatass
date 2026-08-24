import fatass
from fatass.topology.examples.writings.seminar.materials import Node as Materials
from fatass.topology.examples.writings.seminar.skeleton import Node as Skeleton
from fatass.topology.examples.writings.seminar.style import Node as Style


def build(skeleton: Skeleton, style: Style, materials: Materials):
    plan = fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[skeleton],
        prompt=(
            f"Read `skeleton.md` in the readable directory for this node's "
            f"`skeleton` dependency: it holds one entry per paragraph of "
            f"the essay, each a self-contained prompt stating what that "
            f"paragraph must argue or cover, its role relative to its "
            f"neighbors, and the specific claims, evidence, and quotes it "
            f"should draw on.\n\n"
            f"Do not write anything yet. Split skeleton.md into its "
            f"individual entries, in order, without altering their "
            f"content.\n\n"
            f"Write your result as JSON matching this shape to "
            f".fatass-result.json: "
            f'{{"paragraphs": ["<entry 1 text>", "<entry 2 text>", ...]}}.'
        ),
        returns=dict,
    )
    paragraphs = plan["paragraphs"]
    total = len(paragraphs)

    for i, entry in enumerate(paragraphs, start=1):
        if i == 1:
            continuity_note = (
                "This is the first paragraph of the essay — there is no "
                "prior text yet."
            )
            write_instruction = (
                "Write the paragraph to a new file `draft.md` in the "
                "current directory."
            )
        else:
            continuity_note = (
                f"Read `draft.md` in the current directory: it holds "
                f"paragraphs 1 through {i - 1} of the essay, written so "
                f"far by earlier steps. The new paragraph must follow on "
                f"from it naturally."
            )
            write_instruction = (
                "Append the paragraph to the end of `draft.md` in the "
                "current directory, separated from what's already there by "
                "a blank line."
            )

        fatass.free(
            silent=True,
            model="opus",
            tools="Read,Write,Edit,Glob,Grep,Bash",  # Bash: the subject/reference PDFs under `materials` need it, else Read misreads them as password-protected
            readable=[style, materials],
            prompt=(
                f"{continuity_note}\n\n"
                f"Also read every file in the readable directory for this "
                f"node's `style` dependency, including its sub nodes: "
                f"`style/tone/questionnaire.md` and "
                f"`style/narrative/questionnaire.md` (the desired tone and "
                f"narrative style, as filled out) and any material under "
                f"`ai_pattern/` (patterns of AI-sounding writing to avoid). "
                f"Together these define the style the essay must be written "
                f"in.\n\n"
                f"Also read the readable directory for this node's "
                f"`materials` dependency, including its sub nodes: "
                f"`papers/subject/` (the original subject paper) and "
                f"`papers/references/` (each original reference paper). "
                f"These are the primary sources — use them only as "
                f"reference to check that a claim, quote, or piece of "
                f"evidence named below is rendered accurately; do not draw "
                f"in claims or evidence beyond what's given below.\n\n"
                f"This is paragraph {i} of {total} in the essay. Here is "
                f"its skeleton entry, stating what it must argue or cover "
                f"and the specific claims, evidence, and quotes it should "
                f"draw on:\n\n{entry}\n\n"
                f"Write this paragraph as actual prose, using only the "
                f"context inlined above — do not invent claims or evidence "
                f"beyond what it gives you. Apply the style consistently "
                f"with the paragraphs already written: match the tone and "
                f"narrative style described in the questionnaires, and "
                f"avoid the AI-sounding patterns noted under ai_pattern/.\n\n"
                f"{write_instruction} Write only the paragraph's prose — no "
                f"heading, entry title, or other scaffolding — so draft.md "
                f"keeps reading as a single continuous essay draft, not an "
                f"annotated outline."
            ),
        )
