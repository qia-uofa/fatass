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
            f"If the CV is present but has no independent or personal "
            f"projects, open-source contributions, or side projects not "
            f"tied to a formal position or already-listed publication, "
            f"also do nothing and write nothing — do not create "
            f"`from_current_cv.md`.\n\n"
            f"Otherwise, extract every such project mentioned: its dates "
            f"and a brief description, for each one. Extract only what the "
            f"CV actually states — never infer or add a detail it doesn't "
            f"mention.\n\n"
            f"Write the extracted entries to `from_current_cv.md` in the "
            f"current directory, one entry per project. The candidate may "
            f"already have other files in this directory, including "
            f"entries added by hand — do not touch, overwrite, or read "
            f"from any file other than `from_current_cv.md` itself; both "
            f"sources are meant to coexist."
        ),
    )
