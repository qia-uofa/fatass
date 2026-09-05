import fatass
from fatass.topology.archive.thesis.experiment.docs.paper import Paper as Paper
from fatass.topology.archive.thesis.experiment.docs.manual import Manual as Experiment


def build(paper: Paper):
    print("Starting build: writing experiment guidebook from paper")
    guidebook = fatass.free(
        readable=[paper],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="opus",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt="""
paper depends on node `thesis.replication.paper` — read the paper file in
its readable directory (it may be a PDF or another format; if Read
struggles with a PDF, fall back to Bash to extract its text).

Produce a complete, self-contained reproduction guidebook covering every
experiment described in the paper. Someone with no access to the paper
itself must be able to reproduce every experiment using only this
guidebook — so extract and restate, in your own words, everything needed:
research questions/hypotheses, datasets (sources, versions, splits,
preprocessing steps), models/systems under test and their configurations,
hyperparameters, environment/dependencies, exact procedure for running
each experiment, evaluation metrics and how they're computed, and how to
interpret/validate results against the paper's reported findings.

Organize it as one Markdown document with a section per experiment (or a
shared setup section followed by per-experiment sections, if the paper's
experiments share common setup). Do not just summarize the paper's prose
— write actionable, step-by-step instructions a competent researcher can
follow directly.

Report the finished guidebook's full Markdown content as your result.
""",
    )
    print("Writing guidebook to _.md")
    (Experiment()._assets_dir() / "_.md").write_text(guidebook, encoding="utf-8")
    print("Build complete")
