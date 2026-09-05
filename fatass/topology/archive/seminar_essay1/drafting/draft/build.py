import fatass
from .draft import Draft
from fatass.topology.archive.seminar_essay1.papers import Papers as Papers
from fatass.topology.archive.seminar_essay1.analysis import Analysis as Analysis
from fatass.topology.archive.seminar_essay1.drafting.structure import Structure as Structure


def build(papers: Papers, analysis: Analysis, structure: Structure):
    draft = Draft()
    structure_dir = structure._assets_dir()
    overview = (structure_dir / "_.md").read_text(encoding="utf-8")

    paragraph_files = sorted(
        (p for p in structure_dir.glob("*.md") if p.stem.isdigit()),
        key=lambda p: int(p.stem),
    )

    print(f"build@draft: {len(paragraph_files)} paragraph prompt(s) found in structure/")

    draft_path = draft._assets_dir() / "_.md"
    draft_text = ""

    for paragraph_file in paragraph_files:
        paragraph_prompt = paragraph_file.read_text(encoding="utf-8")
        print(f"build@draft: generating paragraph {paragraph_file.stem} ({paragraph_file.name})")

        paragraph = fatass.free(
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            effort="high",
            tools="Read,Write,Edit,Glob,Grep,Bash",
            returns=str,
            readable=[papers, analysis, structure],
            prompt=f"""
You are drafting one paragraph of a seminar essay, autoregressively, one
paragraph at a time. The essay's focus is the ANALYSIS of the seminar's
papers and presentations, not a restatement of the papers themselves.

Write from the POV of the student who presented the subject paper —
first person, as the presenter reflecting on and analyzing their own
paper and how it connects to the other papers/presentations in the
seminar, not as a neutral outside observer.

Essay overview (structure's own summary, for context on where this
paragraph fits in the whole essay):

{overview}

--- Essay written so far ---
{draft_text if draft_text.strip() else "(nothing written yet — this is the opening paragraph)"}
--- end of essay written so far ---

This paragraph's prompt and target word count (from structure/{paragraph_file.name}):

{paragraph_prompt}

Dependencies you have read access to:
- `papers` — a Chain; each item has `metadata` (including the
  presenting student's name and the paper's citation info), `pdf` (the
  paper itself), and `sidenotes` (that student's seminar presentation
  notes on the paper). Use papers only as a sanity check for factual
  claims — do not summarize them at length. When referring to a paper's
  presentation or a claim traceable to a specific presenter, refer to
  the student by name (from their `metadata`), not by paper title alone.
- `analysis` — holds `interconnection` (sidenote <-> paper: how a
  student's presentation/sidenotes relate to the paper they presented),
  `intraconnection` (reference paper <-> subject paper: how papers relate
  to each other), and `summary`. This is the primary source for this
  paragraph's content — the essay should be built from this analysis,
  papers are for verification only.
- `structure` — the essay's own outline (this same directory); you have
  read access to the other paragraph prompts too, for continuity, but
  write only the one paragraph asked for here.

Write ONLY the next paragraph (continuing directly from the essay so
far, matching its voice and not repeating earlier material), hitting the
target word count from the paragraph prompt above as closely as
reasonable. Report the paragraph's plain text (markdown prose, no
heading) as your result — do not write any files yourself.
""",
        )

        draft_text = f"{draft_text}\n\n{paragraph.strip()}" if draft_text.strip() else paragraph.strip()
        draft_path.write_text(draft_text, encoding="utf-8")
        print(f"build@draft: wrote paragraph {paragraph_file.stem} to {draft_path}")

    print(f"build@draft: done, {len(paragraph_files)} paragraph(s) written to {draft_path}")
