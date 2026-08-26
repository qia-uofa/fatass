import json

import fatass

from .analysis import Analysis
from fatass.topology.seminar_essay.papers import Papers as Papers


def _item_paths(index: int) -> str:
    prefix = ".next/" * (index + 1)
    return (
        f"metadata file at papers/{prefix}metadata/_.json, "
        f"pdf file at papers/{prefix}pdf/_.pdf, "
        f"sidenote file at papers/{prefix}sidenote/_.* (extension varies: "
        f".md, .pdf, or .pptx)"
    )


def _read_metadata(papers: Papers, index: int) -> dict:
    path = papers[index].metadata._assets_dir() / "_.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_text(value: str | dict) -> str:
    return value if isinstance(value, str) else json.dumps(value, indent=2)


def build(papers: Papers):
    length = papers.length()
    print(f"analysis.build: found {length} paper(s) in papers")

    metadatas = [_read_metadata(papers, i) for i in range(length)]
    subject_index = next(
        i for i, m in enumerate(metadatas) if m["paper_role"] == "subject"
    )
    subject_title = metadatas[subject_index]["paper_title"]
    print(f"analysis.build: subject paper is index {subject_index} ({subject_title!r})")

    analysis = Analysis()

    for i in range(length):
        print(f"analysis.build: processing item {i} of {length - 1}")
        analysis.extend()
        item = analysis[i]
        meta = metadatas[i]
        paths = _item_paths(i)

        summary_path = item.summary._assets_dir() / "_.md"
        if summary_path.exists():
            print(f"analysis.build: item {i} summary/_.md already exists, skipping")
        else:
            summary = fatass.free(
                readable=[papers],
                returns=dict,
                silent=True,
                permission_mode="bypassPermissions",
                model="sonnet",
                tools="Read,Write,Bash,Glob,Grep",
                prompt=(
                    f"papers is a NodeList (dependency `seminar_essay.materials.papers`); "
                    f"look at item index {i}, whose {paths}. "
                    f"Metadata: {json.dumps(meta)}. "
                    f"Read the paper pdf and the student's sidenote file. "
                    f"Write a short summary of the paper AND of the student's sidenote "
                    f"content, as nested markdown bullet points (a handful of top-level "
                    f"bullets, each with a few nested sub-bullets at most). No prose "
                    f"paragraphs. Return only a raw JSON object of the form "
                    f'{{"markdown": "..."}} containing that markdown, nothing else.'
                ),
            )
            print(f"analysis.build: writing item {i} summary/_.md")
            summary_path.write_text(_coerce_text(summary["markdown"]), encoding="utf-8")

        facts_path = item.facts._assets_dir() / "_.json"
        if facts_path.exists():
            print(f"analysis.build: item {i} facts/_.json already exists, skipping")
        else:
            facts = fatass.free(
                readable=[papers],
                returns=dict,
                silent=True,
                permission_mode="bypassPermissions",
                model="sonnet",
                tools="Read,Write,Bash,Glob,Grep",
                prompt=(
                    f"papers is a NodeList (dependency `seminar_essay.materials.papers`); "
                    f"look at item index {i}, whose {paths}. "
                    f"Metadata: {json.dumps(meta)}. "
                    f"Read the paper pdf and the student's sidenote file. "
                    f"Extract a few short structured facts from the paper and the "
                    f"sidenote (e.g. paper's main claim, method, key result, and the "
                    f"student's takeaway) into a flat JSON object. Keep every value "
                    f"terse -- a short phrase, not a sentence. "
                    f"Return only the raw JSON object, nothing else."
                ),
            )
            print(f"analysis.build: writing item {i} facts/_.json")
            facts_path.write_text(json.dumps(facts, indent=2), encoding="utf-8")

        intraconnection_path = item.intraconnection._assets_dir() / "_.md"
        if intraconnection_path.exists():
            print(f"analysis.build: item {i} intraconnection/_.md already exists, skipping")
        else:
            intraconnection = fatass.free(
                readable=[papers],
                returns=dict,
                silent=True,
                permission_mode="bypassPermissions",
                model="sonnet",
                tools="Read,Write,Bash,Glob,Grep",
                prompt=(
                    f"papers is a NodeList (dependency `seminar_essay.materials.papers`); "
                    f"look at item index {i}, whose {paths}. "
                    f"Metadata: {json.dumps(meta)}. "
                    f"Read the paper pdf and the student's sidenote file. "
                    f"Write a short nested markdown bullet list of how the student's "
                    f"sidenote connects to its own paper. No prose paragraphs. "
                    f"Return only a raw JSON object of the form "
                    f'{{"markdown": "..."}} containing that markdown, nothing else.'
                ),
            )
            print(f"analysis.build: writing item {i} intraconnection/_.md")
            intraconnection_path.write_text(
                _coerce_text(intraconnection["markdown"]), encoding="utf-8"
            )

        interconnection_path = item.interconnection._assets_dir() / "_.md"
        if interconnection_path.exists():
            print(f"analysis.build: item {i} interconnection/_.md already exists, skipping")
        elif i == subject_index:
            print(f"analysis.build: item {i} is the subject paper, skipping interconnection call")
            interconnection = (
                "- this is the subject paper itself, so there is no other "
                "subject paper to connect it to"
            )
            print(f"analysis.build: writing item {i} interconnection/_.md")
            interconnection_path.write_text(_coerce_text(interconnection), encoding="utf-8")
        else:
            interconnection = fatass.free(
                readable=[papers],
                returns=dict,
                silent=True,
                permission_mode="bypassPermissions",
                model="sonnet",
                tools="Read,Write,Bash,Glob,Grep",
                prompt=(
                    f"papers is a NodeList (dependency `seminar_essay.materials.papers`); "
                    f"look at item index {i}, whose {paths}. "
                    f"Metadata: {json.dumps(meta)}. "
                    f"The subject paper is item index {subject_index}, titled "
                    f"{subject_title!r} (same paths pattern, {_item_paths(subject_index)}). "
                    f"Read both papers' pdfs. Write a short nested markdown bullet "
                    f"list of how this paper (item {i}) connects to the subject "
                    f"paper. No prose paragraphs. Return only a raw JSON object of "
                    f'the form {{"markdown": "..."}} containing that markdown, '
                    f"nothing else."
                ),
            )
            print(f"analysis.build: writing item {i} interconnection/_.md")
            interconnection_path.write_text(
                _coerce_text(interconnection["markdown"]), encoding="utf-8"
            )

    print("analysis.build: done")
