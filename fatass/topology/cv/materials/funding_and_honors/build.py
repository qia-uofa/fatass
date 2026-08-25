import fatass
from fatass.topology.cv.current_cv import CurrentCv as CurrentCv


def build(current_cv: CurrentCv):
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Glob,Grep,Bash",  # Bash: the CV under `current_cv` is likely a PDF, else Read misreads it as password-protected
        readable=[current_cv],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`current_cv` dependency — the candidate's existing CV, if "
            f"they have one. That directory may be empty (a candidate "
            f"writing their first academic CV has none): if so, do "
            f"nothing and write nothing.\n\n"
            f"If the CV has neither a grants/funding section nor an "
            f"honors/awards section, also do nothing and write nothing — "
            f"do not create `from_current_cv.md`.\n\n"
            f"Otherwise, extract two kinds of entry, under two clearly "
            f"separate subheadings:\n\n"
            f"1. Every grant or funding award, with the funding body, the "
            f"candidate's role (PI, co-PI, etc.), and dates.\n"
            f"2. Every honor, award, and fellowship, with the awarding "
            f"body and date.\n\n"
            f"Extract only what the CV actually states — never infer or "
            f"add a detail it doesn't mention.\n\n"
            f"Write the extracted entries to `from_current_cv.md` in the "
            f"current directory as two sections, \"## Grants and Funding\" "
            f"and \"## Awards and Honors\", each with one entry per item — "
            f"omit either subheading entirely if the CV has nothing for "
            f"it. The candidate may already have other files in this "
            f"directory, including entries added by hand — do not touch, "
            f"overwrite, or read from any file other than "
            f"`from_current_cv.md` itself; both sources are meant to "
            f"coexist."
        ),
    )
