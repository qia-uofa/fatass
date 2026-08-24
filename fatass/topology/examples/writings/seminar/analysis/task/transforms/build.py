import fatass
from fatass.topology.examples.writings.seminar.materials.task import (
    Node as Task,
)


def build(task: Task):
    fatass.free(
        readable=[task],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`task` dependency: the seminar assignment/task description "
            f"for the essay we are writing.\n\n"
            f"Read the task carefully and analyze exactly what it is "
            f"asking for — the required deliverable, its scope, length, "
            f"grading criteria, and any constraints on structure, "
            f"sources, or argument the task specifies. Note anything "
            f"ambiguous or easy to misread.\n\n"
            f"Then plan the essay's structure: propose a section-by-"
            f"section outline (working titles plus, for each section, "
            f"what it argues or covers and roughly how much weight/space "
            f"it should get relative to the others). The plan's primary "
            f"emphasis must be our subject paper and our own sidenote on "
            f"it — that pairing should anchor the largest and most "
            f"central sections of the essay. Treat material drawn from "
            f"reference papers/sidenotes as supporting or contrasting "
            f"evidence that services the subject-paper argument, not as "
            f"co-equal content, and say explicitly in the plan where and "
            f"why each reference-derived point earns its place. Flag any "
            f"section where the task's own criteria call for emphasis "
            f"other than the subject paper, and explain why.\n\n"
            f"Write a single planning document, `plan.md`, in the current "
            f"directory containing: (1) the task analysis, (2) the "
            f"proposed essay outline with per-section emphasis notes, and "
            f"(3) a short list of open questions or risks a writer should "
            f"resolve before drafting.\n\n"
            f"Finally, write `log.md` in the current directory: a short "
            f"record of what you did — the task file(s) you read and a "
            f"summary of the plan you wrote into plan.md."
        ),
    )
