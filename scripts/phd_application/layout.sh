#!/bin/sh
# Scaffolds the PhD-application topology's shape: every node directory and
# every transform stub, under the entry node `phd_application`. No line here
# calls the Claude CLI — `create <node.path>` and `create <transform>@
# <node.path>` (both without --prompt) only write the boilerplate
# node.py/__init__.py or transform stub and never invoke fatass.free()/
# refine_*, so this script is pure, free, local filesystem setup. See
# phd_application/populate.sh for the companion script that fleshes out each
# transform stub with real logic — those calls do hit the real Claude CLI.
#
# Assumes the shell's cwd is the repo root and FATASS_NODE is already set to
# the project entry node (`phd_application`) — every node.path below is
# written relative to it, with no leading `phd_application.`.
# `phd_application` itself is assumed to already exist.
#
# Shape:
#   profile/       applicant inputs — target preferences + personal materials
#   hunt/          hunting the internet for matching programs/professors
#   outreach/      composing outreach emails and configuring (gated) auto-send

# --- profile: applicant preferences + personal materials, mostly hand-filled -
python -m fatass create profile

# profile.questionnaire is a local survey web app (like coding.spec.app) that
# the applicant runs and fills by hand; on submit it writes preferences.json
# into `profile`'s own nodes/ directory (one level up from the app files).
python -m fatass create profile.questionnaire
python -m fatass create build@profile.questionnaire

# profile.documents.* are raw personal materials, populated by hand by the
# applicant (drop a cv.pdf under profile.documents.cv, etc.) — no build
# transforms, same convention as the thesis example's materials/ subtree.
python -m fatass create profile.documents
python -m fatass create profile.documents.cv
python -m fatass create profile.documents.transcripts
python -m fatass create profile.documents.publications
python -m fatass create profile.documents.writing_sample
python -m fatass create profile.documents.references

# --- hunt: cast a wide net, enrich, then rank -- the emphasis of this project
python -m fatass create hunt
python -m fatass create hunt.landscape
python -m fatass create build@hunt.landscape
python -m fatass create hunt.profiles
python -m fatass create build@hunt.profiles
python -m fatass create hunt.shortlist
python -m fatass create build@hunt.shortlist

# --- outreach: compose personalized emails, gate them, then (safely) send ---
python -m fatass create outreach
python -m fatass create outreach.emails
python -m fatass create build@outreach.emails

# outreach.review is a manual gate, populated by hand by the applicant
# (mark which composed emails are cleared to send) — no build transform,
# same "populated by hand" convention as profile.documents.*.
python -m fatass create outreach.review

python -m fatass create outreach.dispatch
python -m fatass create build@outreach.dispatch
