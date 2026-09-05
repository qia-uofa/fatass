import fatass
from fatass.topology.archive.thesis.experiment.docs.manual import Manual as Manual
from fatass.topology.archive.thesis.experiment.scripts.setup import Setup as Setup


def build(manual: Manual, setup: Setup):
    print("build: starting code base generation from manual")
    fatass.free(
        readable=[manual, setup],
        silent=False,
        permission_mode="bypassPermissions",
        model="opus",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt="""
manual depends on node `thesis.experiment.docs.manual` — read `_.md` in
its readable directory: a self-contained reproduction guidebook covering
every experiment described in the paper, organized as a shared setup
section (if any) followed by one section per experiment — research
questions/hypotheses, datasets, models/systems and their configurations,
hyperparameters, environment/dependencies, the exact procedure for
running each experiment, evaluation metrics and how they're computed,
and how to interpret/validate results against the paper's reported
findings.

setup depends on node `thesis.experiment.scripts.setup` — read `_.sh` in
its readable directory: the shell script that provisions this
experiment's environment (runtimes/packages, the filesystem layout,
environment variables, datasets). Assume this script has already run
successfully on the machine you're working on — the packages, directory
layout, environment variables, and datasets it sets up already exist.
Do not re-implement, call, or duplicate anything it does; only rely on
the state it leaves behind, using its paths verbatim.

Build a Python code base in your own writable directory, strictly
following the manual:

1. A Python module (or package, if the manual's scope warrants splitting
   across multiple files) implementing everything the manual's shared
   setup section and per-experiment sections describe as code: loading
   the datasets/models they name (from the filesystem layout setup.sh
   already created), running each experiment's exact procedure, and
   computing each experiment's evaluation metrics. Follow the manual's
   naming, structure, hyperparameters, and configuration exactly — do not
   invent behavior it doesn't describe, and do not guess at paths,
   package names, or data sources it doesn't name. Run on CUDA: any
   model/tensor computation must execute on the GPU (e.g. a
   `torch.device("cuda")` — or the equivalent for whatever framework the
   manual's environment section names — with model, inputs, and any
   other tensors moved to it) rather than defaulting to CPU; only fall
   back to CPU for a step the manual itself describes as CPU-only.

2. For each experiment section in the manual, one Jupyter notebook that
   imports the module built in step 1, runs that experiment end-to-end
   using the module's functions, computes its evaluation metrics, and
   visualizes the results (e.g. plots/tables comparing against the
   paper's reported findings where the manual gives a figure or number to
   validate against). Name each notebook after its experiment.

3. A `pytest` test suite covering the module built in step 1 — unit tests
   for its individual functions (data loading/preprocessing, procedure
   steps, metric computations, etc.), using small synthetic or fixture
   inputs rather than depending on the full datasets/models being present.
   Do not write tests for the notebooks themselves.

Keep a clear separation between the reusable module, the per-experiment
notebooks, and the test suite. Actually run `pytest` and execute each
notebook end-to-end before finishing (e.g. via `jupyter nbconvert
--to notebook --execute`) to confirm imports resolve, all tests pass, and
every notebook cell runs against the module without error, rather than
merely looking plausible; fix any failure you find and re-run until both
pass.
""",
    )
    print("build: code base generation complete")
