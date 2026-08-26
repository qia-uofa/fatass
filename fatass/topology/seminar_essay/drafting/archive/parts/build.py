import json
import re

import fatass

from .parts import Parts
from fatass.topology.seminar_essay.drafting.structure import Structure as Structure
from fatass.topology.seminar_essay.analysis import Analysis as Analysis
from fatass.topology.seminar_essay.papers import Papers as Papers


def _subject_index(papers: Papers) -> int:
    for i in range(papers.length()):
        meta = json.loads((papers[i].metadata._assets_dir() / "_.json").read_text(encoding="utf-8"))
        if meta["paper_role"] == "subject":
            return i
    raise ValueError("no subject paper found in papers")


def build(structure: Structure, analysis: Analysis, papers: Papers):
    print("Reading structure's outline and splitting it into parts by '##' headings")
    outline = (structure._assets_dir() / "_.md").read_text(encoding="utf-8")

    sections = [s for s in re.split(r"(?m)^##\s+", outline) if s.strip()]

    length = papers.length()
    subject_index = _subject_index(papers)
    print(f"drafting.parts.build: subject paper is analysis item {subject_index} of {length}")

    analysis_readable = []
    for i in range(length):
        item = analysis[i]
        analysis_readable.extend(
            [item.summary, item.facts, item.intraconnection, item.interconnection]
        )

    parts = Parts()
    for i, section in enumerate(sections):
        title, _, body = section.partition("\n")
        title = title.strip()
        body = body.strip()

        match = re.search(r"(\d+)\s*words?", title, re.IGNORECASE)
        wordcount = int(match.group(1)) if match else None
        wordcount_note = f"about {wordcount} words" if wordcount else "an appropriate length"

        part_path = parts._assets_dir() / f"{i}.md"
        if part_path.exists():
            print(f"Skipping part {i} ({title!r}) - already written")
            continue

        print(f"Writing part {i} ({title!r}, {wordcount_note})")
        paragraph = fatass.free(
            readable=analysis_readable,
            returns=str,
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            tools="Read,Write,Glob,Grep",
            prompt=(
                "Write a single paragraph of a seminar essay draft, "
                f"{wordcount_note}, for this outline section:\n\n"
                f"## {title}\n{body}\n\n"
                "`analysis`, node `seminar_essay.materials.analysis`, is your context — it is "
                f"a list of {length} items, one per session paper; item {subject_index} is the "
                "subject/target paper the essay is about, the rest are reference papers it "
                "engages with. For each item's readable directory, the relevant subdirectories "
                "are: `summary/` (summary of that paper), `facts/` (extracted facts about that "
                "paper), `intraconnection/` (connections between that paper and the student's "
                "own presentation/experiment), and `interconnection/` (connections between that "
                "paper and the subject paper — empty/trivial for the subject paper's own item). "
                "Pay close attention to which item is the subject/target paper and which are "
                "reference papers, and do not conflate them.\n\n"
                "Output only the paragraph's prose — no heading, no title, no meta-commentary. "
                "Your final result must be a plain string containing the paragraph text itself, "
                "not a JSON object or dict."
            ),
        )
        part_path.write_text(paragraph, encoding="utf-8")

    print("Done.")
