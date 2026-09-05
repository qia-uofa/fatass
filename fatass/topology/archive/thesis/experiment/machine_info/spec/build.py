import fatass
from fatass.topology.archive.thesis.experiment.docs.spec import Spec as Spec

from .spec import Spec as _Own


def build(spec: Spec):
    print("build: starting info.spec report")
    print("build: invoking agent to read experiment spec and inspect local machine")
    report = fatass.free(
        readable=[spec],
        returns=str,
        silent=False,
        permission_mode="bypassPermissions",
        model="sonnet",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt="""\
Write a reproducibility-assessment report comparing this experiment's
required specification against the machine you are actually running on.

Dependency `thesis.reproduction.experiment.spec` (Spec) is readable at its
own directory, passed to you above — read whatever file(s) it contains
(e.g. hardware/software/dependency requirements for reproducing the
experiment: things like required OS, CPU/GPU, memory, disk, language/
runtime versions, packages). Treat its contents as the ground truth for
what the experiment needs.

Then inspect the local machine you are actually running on, using Bash,
to determine its actual specs — e.g. `uname -a`, `nproc`, `lscpu`,
`free -h`, `df -h`, `python3 --version`, `nvidia-smi` (if present, to
check for a GPU; note its absence otherwise), and any other commands
needed to check specific requirements named in the experiment spec.

Write a markdown report with:
- A summary verdict: does this machine appear to satisfy the experiment's
  requirements, partially, or not at all?
- A table or list comparing each requirement from the experiment spec
  against what was actually found on this machine.
- Any requirements from the spec that could not be verified, and why.

Do not write any files yourself. Report the finished markdown report text
as your result.
""",
    )
    print("build: writing report to _.md")
    (_Own._assets_dir() / "_.md").write_text(report, encoding="utf-8")
    print("build: done")
