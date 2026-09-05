import fatass

from .equations import Equations
from fatass.topology.archive.thesis.experiment.docs.paper import Paper as Paper
from fatass.topology.archive.thesis.experiment.code import Code as Code
from fatass.topology.archive.thesis.experiment.code_morph import CodeMorph as CodeMorph


def build(paper: Paper, code: Code, code_morph: CodeMorph):
    print("equations.build: starting")

    equations = Equations()
    output_path = equations._assets_dir() / "_.md"

    print("equations.build: calling agent to synthesize the equation collection")
    content = fatass.free(
        readable=[paper, code, code_morph],
        returns=str,
        silent=False,
        permission_mode="bypassPermissions",
        model="opus",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt=(
            "You are assembling a self-contained collection of mathematical "
            "equations documenting this thesis's experiment, for a markdown "
            "asset file.\n\n"
            "Dependencies:\n"
            "- `paper` (node `thesis.experiment.docs.paper`): the paper "
            "describing the experiment's full theory/design. Read it for the "
            "formal grounding, terminology, and notation the experiment is "
            "based on.\n"
            "- `code` (node `thesis.experiment.code`): the full, original "
            "experiment implementation. Read it for context on what the "
            "complete experiment does.\n"
            "- `code_morph` (node `thesis.experiment.code_morph`): the "
            "morphed code actually used for THIS thesis. This is the scope "
            "that matters -- it may only implement part of what `code` and "
            "`paper` cover.\n\n"
            "Task: read the paper, the code, and (most importantly) the "
            "morphed code. Then write a coherent collection of mathematical "
            "equations that formalizes what `code_morph` actually does. "
            "Only include equations relevant to logic present in "
            "code_morph -- do not pull in paper/code material that "
            "code_morph does not implement. Any technical detail in the "
            "morphed code can and should be expressed as an equation: not "
            "just loss functions or metrics, but also things like data "
            "transformations, normalization, thresholds, sampling "
            "procedures, statistical tests, or aggregation steps -- if the "
            "code does it, formalize it.\n\n"
            "Structure:\n"
            "- Start with a preliminaries section defining global notation: "
            "shared variables/symbols, sets, and any helper functions used "
            "by more than one later equation, so nothing downstream is "
            "introduced without first being defined.\n"
            "- Then present the equations in the logical order the morphed "
            "code applies them (roughly its data/control flow), each as a "
            "numbered/labeled display equation in LaTeX.\n"
            "- Every equation must be immediately followed by a description "
            "explaining what it computes and why, plus a definition of "
            "every variable/symbol appearing in it that wasn't already "
            "fixed in the preliminaries.\n"
            "- All equations must be mutually coherent: reuse the same "
            "symbol for the same quantity everywhere, never redefine a "
            "symbol to mean something else later, and keep notation "
            "consistent with the paper's own conventions where code_morph "
            "actually follows the paper.\n\n"
            "Return only the raw markdown content for this file (LaTeX "
            "equations in $$...$$ or \\[...\\] display blocks), nothing "
            "else -- no wrapping code fences."
        ),
    )

    print(f"equations.build: writing {output_path}")
    output_path.write_text(content, encoding="utf-8")
    print("equations.build: done")
