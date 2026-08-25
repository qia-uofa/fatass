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
            f"If the CV is present but has no positions/appointments "
            f"section (postdoctoral positions, faculty roles, visiting "
            f"positions, or other academic appointments and employment), "
            f"also do nothing and write nothing — do not create "
            f"`from_current_cv.md`.\n\n"
            f"Otherwise, extract every academic appointment or employment "
            f"entry: institution, title, and dates, for each one. Extract "
            f"only what the CV actually states — never infer or add a "
            f"detail it doesn't mention; omit any of these fields for a "
            f"given entry if the CV doesn't state it.\n\n"
            f"Write the extracted entries to `from_current_cv.md` in the "
            f"current directory, one entry per position. The candidate may "
            f"already have other files in this directory, including "
            f"entries added by hand — do not touch, overwrite, or read "
            f"from any file other than `from_current_cv.md` itself; both "
            f"sources are meant to coexist."
        ),
    )
