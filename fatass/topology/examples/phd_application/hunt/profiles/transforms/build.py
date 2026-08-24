import fatass
from fatass.topology.examples.phd_application.hunt.landscape import Node as Landscape
from fatass.topology.examples.phd_application.profile import Node as Profile


def build(landscape: Landscape, profile: Profile):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        readable=[landscape, profile],
        prompt=(
            f"Read `landscape.json` in the readable directory for this "
            f"node's `landscape` dependency — a JSON array of candidate "
            f"programs/labs/professors surfaced during the longlist search "
            f"— and `preferences.json` in the readable directory for this "
            f"node's `profile` dependency — the applicant's scouting "
            f"questionnaire (target research areas and keywords, "
            f"geographic/visa constraints, funding requirements, "
            f"institution tier tolerance, advisor seniority/lab size "
            f"preference, remote vs. onsite fit, application deadline "
            f"window, max number of targets).\n\n"
            f"For every candidate in `landscape.json`, fetch their faculty/"
            f"lab page and a recent publication listing (their lab site, "
            f"Google Scholar, DBLP, or arXiv author page) and build an "
            f"enriched profile covering:\n"
            f"- their research directions over roughly the last three "
            f"years\n"
            f"- two or three notable recent papers, with titles\n"
            f"- any visible \"accepting students\" or lab-openness signal\n"
            f"- funding status, if stated\n"
            f"- application deadline, if stated\n"
            f"- a short note on fit against `preferences.json`, citing "
            f"specific evidence just gathered\n\n"
            f"If a candidate's page cannot be found or fetched, keep the "
            f"candidate in the output with a `status: \"unreachable\"` "
            f"entry and a one-line reason, rather than dropping it "
            f"silently.\n\n"
            f"Write the result as `profiles.json` in the current "
            f"directory: one enriched object per candidate, keyed by the "
            f"same identity used in `landscape.json`.\n\n"
            f"Also write `log.md` in the current directory recording the "
            f"sources checked per candidate and any candidates marked "
            f"unreachable."
        ),
    )
