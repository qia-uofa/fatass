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
            f"If the CV is present but has neither a teaching section "
            f"(courses taught) nor a service section (committee, "
            f"peer-reviewing, editorial, or other professional service "
            f"roles), also do nothing and write nothing — do not create "
            f"`from_current_cv.md`.\n\n"
            f"Otherwise extract two kinds of entry. First, every course "
            f"taught: institution, the candidate's role (instructor, "
            f"teaching assistant, etc.), and dates, for each one. Second, "
            f"every committee role, peer-reviewing role, editorial role, "
            f"and other professional service entry, with dates. Extract "
            f"only what the CV actually states — never infer or add a "
            f"detail it doesn't mention; omit any field for a given entry "
            f"if the CV doesn't state it.\n\n"
            f"Write the extracted entries to `from_current_cv.md` in the "
            f"current directory as two subheadings, `## Teaching` and "
            f"`## Service`, one entry per item under each — omit either "
            f"subheading entirely if the CV has nothing for it. The "
            f"candidate may already have other files in this directory, "
            f"including entries added by hand — do not touch, overwrite, "
            f"or read from any file other than `from_current_cv.md` "
            f"itself; both sources are meant to coexist."
        ),
    )
