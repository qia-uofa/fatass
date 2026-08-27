import fatass
from fatass.topology.thesis.experiment.docs.manual import Manual as Manual
from .spec import Spec


def build(manual: Manual):
    print("Starting build: extracting spec requirements from manual")
    spec = fatass.free(
        readable=[manual],
        returns=str,
        silent=False,
        model="haiku",
        effort="low",
        tools="Read,Write,Edit,Glob,Grep",
        prompt="""
manual depends on node `thesis.reproduction.experiment.manual` — read the
reproduction guidebook (`_.md`) in its readable directory.

Distill it into a brief requirements report with exactly two sections:

1. Minimum requirement — the smallest set of concrete, checkable
   requirements (datasets, models/systems and configurations,
   hyperparameters, environment/dependencies, evaluation metrics) needed
   to reproduce the guidebook's experiments at all.
2. Recommended requirement — the fuller set of requirements needed to
   reproduce them faithfully/reliably (closer to the original setup:
   exact versions, full datasets/splits, matching hardware, etc.),
   beyond the bare minimum.

Leave out the guidebook's step-by-step narrative instructions and
rationale; each section is a terse, checklist-style list of requirements,
not a how-to guide.

Organize it as one brief Markdown document with those two top-level
sections (each broken down per experiment only if the manual's
experiments genuinely differ; otherwise keep each section a single flat
checklist). Keep the whole document under 500 words total — bullet
points, not prose.

Report the finished report's full Markdown content as your result.
""",
    )
    print("Writing spec to _.md")
    (Spec()._assets_dir() / "_.md").write_text(spec, encoding="utf-8")
    print("Build complete")
