import fatass
from fatass.topology.examples.phd_application.hunt.shortlist import Node as Shortlist
from fatass.topology.examples.phd_application.profile import Node as Profile
from fatass.topology.examples.phd_application.profile.documents import (
    Node as Documents,
)


def build(shortlist: Shortlist, profile: Profile, documents: Documents):
    fatass.free(
        silent=True,
        model="opus",
        tools="Read,Write,Edit,Glob,Grep,Bash",  # Bash: the CV/transcripts/publications under `documents` are likely PDFs, else Read misreads them as password-protected
        readable=[shortlist, profile, documents],
        prompt=(
            f"Read `shortlist.json` in the readable directory for this "
            f"node's `shortlist` dependency — the ranked candidate list, "
            f"each entry with rank, candidate identity, score, rationale "
            f"paragraph, and specific facts to reference in outreach — "
            f"and `preferences.json` in the readable directory for this "
            f"node's `profile` dependency, for the applicant's requested "
            f"outreach tone/formality.\n\n"
            f"The `documents` dependency's readable directory has one "
            f"subdirectory per material — `cv`, `transcripts`, "
            f"`publications`, `writing_sample`, `references` — populated "
            f"by hand by the applicant; read every file present under "
            f"each. Any of these subdirectories may be empty: that is "
            f"expected, not an error, and simply means that material "
            f"isn't available to draw on.\n\n"
            f"For every candidate in `shortlist.json`'s ranked list, "
            f"compose one personalized outreach email:\n"
            f"- A specific, non-generic subject line and body that "
            f"references the professor's real recent work, using the "
            f"rationale and facts already recorded for that candidate in "
            f"`shortlist.json` — not generic praise.\n"
            f"- One or two concrete, real details drawn from the "
            f"applicant's own `cv`, `publications`, or `writing_sample` "
            f"material that state genuine fit with that professor's work.\n"
            f"- Never invent the applicant's credentials or the "
            f"professor's work — only state what the source material "
            f"actually supports. If a document subdirectory needed to "
            f"make a strong connection is empty or thin, write around the "
            f"gap (e.g. lean on whichever material is available, or keep "
            f"that part of the email more general) rather than inventing "
            f"content to fill it.\n"
            f"- Match the tone and formality to `preferences.json`.\n\n"
            f"Write one file per candidate as `emails/<slug>.md` in the "
            f"current directory (a short, filesystem-safe slug derived "
            f"from the candidate's identity), containing the recipient's "
            f"name/email if known from `shortlist.json`, the subject "
            f"line, and the email body.\n\n"
            f"Also write `emails/index.json`: an array with one entry per "
            f"generated email, each giving the slug, recipient, "
            f"institution, and which document kinds (`cv`, `transcripts`, "
            f"`publications`, `writing_sample`, `references`) should be "
            f"attached when the email is sent — based on what that "
            f"candidate's field/context calls for and what material "
            f"actually exists in `documents`.\n\n"
            f"Finally, write `log.md` in the current directory recording "
            f"how many emails were generated, which document kinds were "
            f"available versus empty, and any candidates where a gap in "
            f"the material forced a more general email.\n\n"
            f"This transform only drafts — do not send anything."
        ),
    )
