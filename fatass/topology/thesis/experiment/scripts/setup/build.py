import fatass
from fatass.topology.thesis.experiment.docs.setup_man import SetupMan as SetupMan
from fatass.topology.thesis.experiment.machine_info.filesystem import (
    Filesystem as Filesystem,
)

from .setup import Setup


def build(setup_man: SetupMan, filesystem: Filesystem):
    print("build: starting setup script generation")
    print("build: invoking agent to compose _.sh from the setup manual")
    script = fatass.free(
        readable=[setup_man, filesystem],
        returns=str,
        silent=False,
        permission_mode="bypassPermissions",
        model="sonnet",
        effort="medium",
        tools="Read,Write,Edit,Glob,Grep",
        prompt="""\
Dependency `thesis.experiment.docs.setup_man` (setup_man) is readable at
its own directory, passed to you above — read `_.md`, a setup manual for
getting a machine ready to reproduce this experiment (Requirements,
Filesystem layout, Environment setup, Data setup, and Verification
sections).

Dependency `thesis.experiment.machine_info.filesystem` (filesystem) is
also readable at its own directory, passed to you above — it holds the
machine's actual filesystem layout as explicit, authoritative paths. Use
those paths verbatim wherever the script creates directories or places
data, instead of paraphrasing paths out of setup_man's prose; if
setup_man's Filesystem layout section ever conflicts with it, treat
filesystem's paths as authoritative.

Write the full contents of a single POSIX shell script that provisions
only the *environment* portion of that manual: installing
runtimes/packages, creating the filesystem layout's directories, setting
environment variables, and obtaining/placing any datasets it describes.
Do not clone, build, fetch, or otherwise reference the experiment's own
code — it does not exist on the machine yet and is out of scope for this
script.

The script must serve two uses, both by re-running the exact same file:
1. A fresh run on a brand-new machine, setting up the environment from
   scratch.
2. Restoring the environment on a machine that already has it, e.g.
   after a scratch/tmp filesystem reset wiped ephemeral state (so
   directories under it and any data staged there need recreating /
   re-fetching) while durable state elsewhere (e.g. already-installed
   system packages) is left alone and not reinstalled.
Make every step idempotent and safe to re-run (e.g. `mkdir -p`, check
before installing or downloading something already present) so one
invocation covers both uses without prompting or failing the second
time.

Start the script with `#!/usr/bin/env bash` and `set -euo pipefail`. Add
a short comment above each major step naming what it does and, where
relevant, which section of the manual (or filesystem's own paths) it
came from. Ground every command only in what setup_man and filesystem
actually name (paths, package names, versions, URLs, env var names) —
never invent tooling, package names, paths, or data sources they don't
mention; skip a sub-step entirely rather than guessing if both are
silent on it.

Report the finished script's full contents as your result — raw script
text only, no markdown code fences and no extra commentary.
""",
    )
    print("build: writing setup script to _.sh")
    (Setup()._assets_dir() / "_.sh").write_text(script, encoding="utf-8")
    print("build: done")
