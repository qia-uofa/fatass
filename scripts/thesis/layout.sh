#!/bin/sh
# Scaffolds the bachelor thesis topology's shape: every node directory and
# every transform stub, under the entry node `idea`. No line here calls the
# Claude CLI — `create <node.path>` and `create <transform>@<node.path>`
# (both without --prompt) only write the boilerplate node.py/__init__.py or
# transform stub and never invoke fatass.free()/refine_*, so this script is
# pure, free, local filesystem setup. See thesis/populate.sh for the
# companion script that fleshes out each transform stub with real logic —
# those calls do hit the real Claude CLI.
#
# Assumes the shell's cwd is the repo root and FATASS_NODE is already set to
# the project entry node (`idea`) — every node.path below is written relative
# to it, with no leading `idea.`. `idea` itself is assumed to already exist.

# --- materials: raw inputs, populated by hand, no build transforms ---------
python -m fatass create materials
python -m fatass create materials.proposal
python -m fatass create materials.literature
python -m fatass create materials.literature.corpus
python -m fatass create materials.literature.notes
python -m fatass create materials.dataset
python -m fatass create materials.advisor_feedback

# --- review: literature synthesis and gap analysis --------------------------
python -m fatass create review
python -m fatass create review.synthesis
python -m fatass create build@review.synthesis
python -m fatass create review.gap
python -m fatass create build@review.gap
python -m fatass create review.related_work_plan
python -m fatass create build@review.related_work_plan

# --- design: turns the gap into a concrete, runnable research design -------
python -m fatass create design
python -m fatass create design.questions
python -m fatass create build@design.questions
python -m fatass create design.method
python -m fatass create build@design.method
python -m fatass create design.protocol
python -m fatass create build@design.protocol

# --- experiments: the empirical work -----------------------------------
python -m fatass create experiments
python -m fatass create experiments.harness
python -m fatass create build@experiments.harness
python -m fatass create experiments.pilot
python -m fatass create build@experiments.pilot
python -m fatass create experiments.main_run
python -m fatass create build@experiments.main_run
python -m fatass create experiments.ablations
python -m fatass create build@experiments.ablations
python -m fatass create experiments.analysis
python -m fatass create build@experiments.analysis

# --- style: academic register, thesis formatting, AI-pattern guide ---------
python -m fatass create style
python -m fatass create style.voice
python -m fatass create style.voice.register
python -m fatass create style.voice.convention
python -m fatass create style.ai_pattern

# --- drafting: chapter-by-chapter generation ---------------------------
python -m fatass create drafting
python -m fatass create drafting.outline
python -m fatass create build@drafting.outline
python -m fatass create drafting.chapters
python -m fatass create drafting.chapters.introduction
python -m fatass create build@drafting.chapters.introduction
python -m fatass create drafting.chapters.related_work
python -m fatass create build@drafting.chapters.related_work
python -m fatass create drafting.chapters.methodology
python -m fatass create build@drafting.chapters.methodology
python -m fatass create drafting.chapters.results
python -m fatass create build@drafting.chapters.results
python -m fatass create drafting.chapters.discussion
python -m fatass create build@drafting.chapters.discussion
python -m fatass create drafting.chapters.conclusion
python -m fatass create build@drafting.chapters.conclusion
python -m fatass create drafting.assembly
python -m fatass create build@drafting.assembly
python -m fatass create drafting.annotation
python -m fatass create build@drafting.annotation

# --- audit: AI-pattern cleanup, cross-chapter consistency, human review -----
python -m fatass create audit
python -m fatass create audit.draft
python -m fatass create build@audit.draft
python -m fatass create audit.consistency
python -m fatass create build@audit.consistency
python -m fatass create audit.issues
python -m fatass create audit.draft_star
python -m fatass create build@audit.draft_star

# --- defense: thesis-specific final stage ------------------------------
python -m fatass create defense
python -m fatass create defense.slides
python -m fatass create build@defense.slides
python -m fatass create defense.qa_prep
python -m fatass create build@defense.qa_prep
