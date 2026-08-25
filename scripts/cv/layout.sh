#!/bin/sh
# Scaffolds the academic-CV-writing topology's shape: every node directory
# and every transform stub, under the entry node `cv`. No line here calls
# the Claude CLI — `create <node.path>` and `create <transform>@
# <node.path>` (both without --prompt) only write the boilerplate
# node.py/__init__.py or transform stub and never invoke fatass.free()/
# refine_*, so this script is pure, free, local filesystem setup. See
# cv/populate.sh for the companion script that fleshes out each transform
# stub with real logic — those calls do hit the real Claude CLI.
#
# Assumes the shell's cwd is the repo root. Every node.path below is
# absolute (`~.cv....`), so this runs correctly regardless of whatever
# FATASS_NODE currently is — no `cd` needed first. `~.` ignores the
# current node and resolves from the true topology root (see
# fatass.resolve.cwd.expand), so `cv` is a top-level node (a sibling of
# `examples`, not nested inside it).
#
# Shape:
#   current_cv/   holds the candidate's existing CV file, if they have one
#                 (e.g. current_cv.pdf/.docx/.md) — hand-populated, no
#                 transform of its own, left empty for a candidate writing
#                 their first academic CV. Sits outside materials/ and
#                 feeds it: each materials/* subnode below has its own
#                 build(current_cv) transform that extracts that
#                 category's entries out of it, writing them alongside
#                 (never over) whatever the candidate has already added by
#                 hand.
#   materials/    raw career facts, grouped into 7 folders (see below) —
#                 hand-populated by default, same convention as
#                 phd_application.profile.documents.*, and/or
#                 auto-populated from current_cv/. Three folders bundle
#                 two closely-related fact categories each so the
#                 materials tree doesn't sprawl into ten near-empty
#                 single-purpose folders; the merge is purely about where
#                 the raw facts live — cv.preferences and cv.draft still
#                 treat Publications, Presentations, Grants, Awards,
#                 Teaching, and Service as distinct sections of the
#                 rendered CV.
#     education/
#     positions/                      (academic appointments/employment)
#     publications_and_presentations/ (publications + talks — closely
#                                      related scholarly output)
#     funding_and_honors/             (grants + awards — both recognition/
#                                      funding received)
#     teaching_and_service/           (teaching + committee/reviewing/
#                                      editorial service — both
#                                      institutional contribution beyond
#                                      research)
#     personal_projects/
#     references/
#   preferences/  a local survey app for target field, CV purpose, scope,
#                 citation style, and section order
#   draft/        assembles the CV from materials + preferences
#   audit/        fact-checks the draft against materials and fixes
#                 formatting/consistency issues

python -m fatass create ~.cv

# --- current_cv: the candidate's existing CV, if any, sits outside -------
# --- materials/ and (optionally) populates it — see populate.sh ----------
python -m fatass create ~.cv.current_cv

# --- materials: raw career facts — hand-populated and/or extracted from --
# --- current_cv/ by each subnode's own build(current_cv) transform -------
python -m fatass create ~.cv.materials
python -m fatass create ~.cv.materials.education
python -m fatass create build@~.cv.materials.education
python -m fatass create ~.cv.materials.positions
python -m fatass create build@~.cv.materials.positions
python -m fatass create ~.cv.materials.publications_and_presentations
python -m fatass create build@~.cv.materials.publications_and_presentations
python -m fatass create ~.cv.materials.funding_and_honors
python -m fatass create build@~.cv.materials.funding_and_honors
python -m fatass create ~.cv.materials.teaching_and_service
python -m fatass create build@~.cv.materials.teaching_and_service
python -m fatass create ~.cv.materials.personal_projects
python -m fatass create build@~.cv.materials.personal_projects
python -m fatass create ~.cv.materials.references
python -m fatass create build@~.cv.materials.references

# --- preferences: the survey app the candidate fills out by hand --------
python -m fatass create ~.cv.preferences
python -m fatass create build@~.cv.preferences

# --- draft: assemble the CV from materials + preferences -----------------
python -m fatass create ~.cv.draft
python -m fatass create build@~.cv.draft

# --- audit: fact-check against materials, fix formatting/consistency -----
python -m fatass create ~.cv.audit
python -m fatass create build@~.cv.audit
