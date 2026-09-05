import fatass
from fatass.topology.archive.seminar_essay1.drafting.task import Task as Task


def build(task: Task):
    print("build: reading task node's _.md")

    paragraphs = fatass.free(
        readable=[task],
        returns=list,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        prompt="""task depends on node `seminar_essay.materials.drafting.task` — read `_.md` in its readable directory. That file states the essay assignment/task.

Analyze the task and produce a good paragraph-by-paragraph structure for the essay.

Report your result as a list of strings: first a brief overall summary (thesis statement, total target word count, number of paragraphs), then one entry per paragraph, each a markdown section with:
- Content: what the paragraph argues or covers
- Function: its role in the essay's overall argument (e.g. introduces thesis, provides evidence, addresses counterargument, transitions, concludes)
- Word count: a target word count for the paragraph""",
    )

    assets_dir = fatass.topology.archive.seminar_essay1.drafting.structure.Structure()._assets_dir()
    summary, *body_paragraphs = paragraphs

    print("build: writing _.md")
    (assets_dir / "_.md").write_text(summary, encoding="utf-8")

    for i, paragraph in enumerate(body_paragraphs, start=1):
        print(f"build: writing {i}.md")
        (assets_dir / f"{i}.md").write_text(paragraph, encoding="utf-8")

    print("build: done")
