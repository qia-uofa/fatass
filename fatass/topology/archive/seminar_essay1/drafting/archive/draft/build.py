import fatass
from fatass.topology.archive.seminar_essay1.drafting.archive.draft import Draft as Draft
from fatass.topology.archive.seminar_essay1.drafting.archive.parts import Parts as Parts


def build(parts: Parts):
    print("build@draft: starting")

    parts_dir = parts._assets_dir()
    output_path = Draft()._assets_dir() / "_.md"
    if output_path.exists():
        output_path.write_text("", encoding="utf-8")

    i = 0
    while (parts_dir / f"{i}.md").exists():
        part_path = parts_dir / f"{i}.md"
        print(f"build@draft: merging {part_path.name}")

        part_text = part_path.read_text(encoding="utf-8")
        essay_so_far = output_path.read_text(encoding="utf-8") if output_path.exists() else ""

        merged = fatass.free(
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            effort="low",
            tools="Read,Write,Edit,Grep",
            readable=[],
            returns=str,
            prompt=(
                "You are stitching together an essay that was drafted "
                "independently, part by part, into one continuous document.\n\n"
                "Here is the essay so far:\n---\n"
                f"{essay_so_far}\n---\n\n"
                "Here is the next part to append:\n---\n"
                f"{part_text}\n---\n\n"
                "Append the next part to the essay so far, making only minimal "
                "changes to the next part (ideally none) — just enough to smooth "
                "the transition (e.g. removing a redundant heading, fixing a "
                "dangling transition sentence). Do not rewrite, summarize, or "
                "restructure either part. Return the full combined text."
            ),
        )

        output_path.write_text(merged, encoding="utf-8")
        i += 1

    print(f"build@draft: wrote {output_path}")
