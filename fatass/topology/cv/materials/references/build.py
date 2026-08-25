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
            f"If the CV is present but lists no referees explicitly (many "
            f"CVs simply say something like 'available upon request' "
            f"instead of listing referees), also do nothing and write "
            f"nothing — do not create `from_current_cv.md`.\n\n"
            f"Otherwise, extract every referee explicitly listed: name, "
            f"affiliation, and contact, for each one. Extract only what "
            f"the CV actually states — never infer or add a detail it "
            f"doesn't mention; omit any of these fields for a given "
            f"referee if the CV doesn't state it.\n\n"
            f"Write the extracted entries to `from_current_cv.md` in the "
            f"current directory, one entry per referee. The candidate may "
            f"already have other files in this directory, including "
            f"entries added by hand — do not touch, overwrite, or read "
            f"from any file other than `from_current_cv.md` itself; both "
            f"sources are meant to coexist."
        ),
    )
