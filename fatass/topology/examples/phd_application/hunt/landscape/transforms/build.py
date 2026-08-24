import fatass
from fatass.topology.examples.phd_application.profile import Node as Profile


def build(profile: Profile):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        readable=[profile],
        prompt=(
            f"Read `preferences.json` in the readable directory for this "
            f"node's `profile` dependency — it holds a PhD applicant's "
            f"filled-out scouting questionnaire (target research areas and "
            f"keywords, geographic/visa constraints, funding requirements, "
            f"institution tier tolerance, advisor seniority/lab size "
            f"preference, remote vs. onsite fit, application deadline "
            f"window, max number of targets, and a free-text list of "
            f"professors/labs/institutions the applicant already knows "
            f"about).\n\n"
            f"Search the open web — university and department directories, "
            f"faculty listing pages, lab pages, Google Scholar, DBLP, "
            f"OpenReview, arXiv author pages, and PhD-position aggregator "
            f"sites — for graduate programs, labs, and individual "
            f"professors whose research plausibly matches the target "
            f"research areas and keywords in `preferences.json`. Respect "
            f"its stated geographic, funding, and timeline constraints. "
            f"Cast a wide net: this stage is a longlist, not a shortlist. "
            f"Skip anything already named in the applicant's free-text "
            f"list of known professors/labs/institutions.\n\n"
            f"For each candidate found, capture:\n"
            f"- institution\n"
            f"- department/program\n"
            f"- professor name(s), if identifiable\n"
            f"- program or faculty page URL\n"
            f"- the specific fit signal that surfaced it (e.g. a paper, "
            f"research statement, or lab focus matching a target keyword)\n"
            f"- any funding/admission notes visible on the page\n\n"
            f"Write the result as `landscape.json` in the current "
            f"directory: a JSON array of candidate objects with those "
            f"fields.\n\n"
            f"Also write `log.md` in the current directory recording the "
            f"search queries you ran, the sources you checked, and the "
            f"total number of candidates found."
        ),
    )
