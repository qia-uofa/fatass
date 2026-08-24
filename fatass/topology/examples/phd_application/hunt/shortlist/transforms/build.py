import fatass
from fatass.topology.examples.phd_application.hunt.profiles import Node as Profiles
from fatass.topology.examples.phd_application.profile import Node as Profile


def build(profiles: Profiles, profile: Profile):
    fatass.free(
        readable=[profiles, profile],
        prompt=(
            f"Read `profiles.json` in the readable directory for this "
            f"node's `profiles` dependency — one enriched object per "
            f"candidate program/lab/professor, including a `status: "
            f"\"unreachable\"` marker for candidates whose page couldn't be "
            f"fetched — and `preferences.json` in the readable directory "
            f"for this node's `profile` dependency — the applicant's "
            f"scouting questionnaire (target research areas and keywords, "
            f"geographic/visa constraints, funding requirements, "
            f"institution tier tolerance, advisor seniority/lab size "
            f"preference, remote vs. onsite fit, application deadline "
            f"window, max number of targets).\n\n"
            f"Drop every candidate marked `status: \"unreachable\"` in "
            f"`profiles.json` from consideration entirely — do not score "
            f"or exclude-with-reason them, just leave them out of both "
            f"output lists.\n\n"
            f"For every remaining candidate, first check for a hard "
            f"disqualifier: no funding when `preferences.json` requires "
            f"fully-funded, an application deadline that has already "
            f"passed, or the candidate's page explicitly stating they are "
            f"not accepting students. Any candidate with a hard "
            f"disqualifier does not get scored — put it in a separate "
            f"`excluded` list instead, with its identity and the specific "
            f"reason.\n\n"
            f"Score every surviving candidate 1-5 on probable fit and "
            f"likelihood of a successful application, weighing research "
            f"fit, funding availability, deadline feasibility, "
            f"institution-tier tolerance, and geography exactly as "
            f"`preferences.json` states them — use its stated priorities "
            f"and tolerances to decide how heavily each factor counts, "
            f"rather than weighing them evenly by default. Write one "
            f"rationale paragraph per scored candidate that cites specific "
            f"facts from `profiles.json` (research directions, named "
            f"papers, funding/deadline/openness signals).\n\n"
            f"Rank the scored candidates by score descending. Cap the "
            f"ranked list at the max program count stated in "
            f"`preferences.json`, or top 20 if it states none.\n\n"
            f"Write the result as `shortlist.json` in the current "
            f"directory: an object with a ranked array (each entry: rank, "
            f"candidate identity, score, rationale paragraph, and the "
            f"specific facts to reference in outreach) and an `excluded` "
            f"array (each entry: candidate identity and disqualifier "
            f"reason).\n\n"
            f"Also write a human-readable `shortlist.md` in the current "
            f"directory presenting the same ranked list and excluded list "
            f"in Markdown, and a `log.md` recording how many candidates "
            f"were dropped as unreachable, how many were excluded and why, "
            f"and how many were scored and ranked."
        ),
    )
