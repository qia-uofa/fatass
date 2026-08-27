import fatass
from fatass.topology.thesis.experiment.machine_info.spec import Spec as Spec
from fatass.topology.thesis.experiment.docs.manual import Manual as Manual

from .setup_man import SetupMan


def build(spec: Spec, manual: Manual):
    print("build: starting setup manual composition")
    print("build: invoking agent to compose setup manual from spec and manual")
    setup_manual = fatass.free(
        readable=[spec, manual],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        effort="medium",
        tools="Read,Write,Edit,Glob,Grep",
        prompt="""\
Compose a setup manual for getting a machine ready to reproduce this
experiment. Aim for moderate length — a researcher should be able to
work through it start to finish in well under an hour, not an
exhaustive reference.

Dependency `thesis.experiment.machine_info.spec` (spec) is readable at
its own directory, passed to you above — read `_.md`, a
reproducibility-assessment report comparing the experiment's
hardware/software requirements against a real machine it was checked
against. Use it to state what this experiment actually needs (OS,
CPU/GPU, memory, disk, language/runtime versions, packages) and to flag
anything that report found missing, unmet, or unverifiable.

Dependency `thesis.experiment.docs.manual` (manual) is readable at its
own directory, passed to you above — read `_.md`, a full reproduction
guidebook covering every experiment described in the underlying paper
(datasets, models, hyperparameters, procedures, evaluation metrics). Do
not restate it in full; extract only what's needed to get a machine
ready to run those experiments.

Write one self-contained Markdown document with these sections:
- Overview: one short paragraph on what this experiment is and what
  this manual sets up.
- Requirements: the hardware/software/dependency requirements from the
  spec report, and its verdict on whether they're currently met.
- Filesystem layout: a concrete directory layout for the machine being
  set up — where to place the cloned/placed code, datasets, model
  weights/checkpoints, and experiment outputs/results, plus any
  environment variables or config entries that point tools at those
  paths. Use exact paths/variable names only when the spec report or
  guidebook actually name them; otherwise propose a sensible layout
  (e.g. a single project root with code/, data/, checkpoints/, and
  results/ subdirectories) and state it as a recommendation, and make
  every later step reference these paths consistently rather than
  inventing new ones.
- Environment setup: concrete, ordered steps to prepare a machine (e.g.
  installing runtimes, packages, cloning/placing code at the paths from
  Filesystem layout, configuring environment variables) — grounded only
  in what the spec report and guidebook actually name, never invented
  tooling.
- Data setup: how to obtain and place any datasets the guidebook
  describes at the paths from Filesystem layout, if applicable.
- Verification: a short checklist or set of commands to confirm the
  environment and filesystem layout are ready before attempting to run
  any experiment.
- Next steps: point the reader to the full reproduction guidebook for
  actually running the experiments, once setup is verified.

Report the finished manual's full Markdown content as your result.
""",
    )
    print("build: writing setup manual to _.md")
    (SetupMan()._assets_dir() / "_.md").write_text(setup_manual, encoding="utf-8")
    print("build: done")
