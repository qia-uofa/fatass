import fatass
from fatass.topology.examples.coding.spec import Spec as Spec


def build(spec: Spec, side_note: str = ""):
    note = f"\n\nAdditional note to take into account: {side_note}\n" if side_note else ""

    plan = fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[spec],
        prompt=(
            f"Read `spec.json` in the readable directory for this node's "
            f"`spec` dependency — it holds the product spec (sections, "
            f"requirements, constraints, etc.) captured for this project.\n\n"
            f"Do not write anything yet. Your only job right now is to plan "
            f"the structure of a blueprint document set that will later be "
            f"written from this spec. The blueprint is intended for an AI "
            f"coding agent to read and generate the actual source code from, "
            f"so its eventual content must be unambiguous and complete enough "
            f"that no further product decisions are needed to start "
            f"implementing: concrete file/module layout, data models and "
            f"schemas, APIs/interfaces (inputs, outputs, error cases), core "
            f"algorithms or business logic, external dependencies, and how "
            f"the pieces connect to each other end to end.\n\n"
            f"Decide a concrete file layout for the blueprint itself (e.g. "
            f"`01-overview.md`, `02-architecture.md`, `03-data-model.md`, "
            f"one file per major component, etc.) sized to what THIS "
            f"product actually needs — a small product might need three or "
            f"four files, a product with several independent subsystems "
            f"might need one file per subsystem plus shared overview/"
            f"architecture files. For each file, list the sections it will "
            f"contain, and for each section give a title and a concrete "
            f"description of exactly what it must cover and which parts of "
            f"the spec it must be derived from (specific requirements, "
            f"constraints, or components named in spec.json — not generic "
            f"placeholders)."
            + note
            + f"\n\nWrite your result as JSON matching this shape to "
            f"`.fatass-result.json`: "
            f'{{"files": [{{"filename": "01-overview.md", "sections": '
            f'[{{"title": "...", "covers": "..."}}]}}]}}. '
            f"Do not create any other files."
        ),
        returns=dict,
    )

    files = plan["files"]
    filenames = [f["filename"] for f in files]

    for file in files:
        filename = file["filename"]
        sections = file["sections"]
        section_list = "\n".join(
            f"- **{s['title']}**: {s['covers']}" for s in sections
        )
        others = [name for name in filenames if name != filename]
        others_note = (
            f"Other blueprint files already planned (some may not exist yet "
            f"if they haven't been written): {', '.join(others)}. Reference "
            f"them by name where relevant (e.g. \"see 02-architecture.md for "
            f"the request schema\") rather than duplicating their content.\n\n"
            if others
            else ""
        )

        fatass.free(
            silent=True,
            model="sonnet",
            tools="Read,Write,Edit,Glob,Grep",
            readable=[spec],
            prompt=(
                f"Read `spec.json` in the readable directory for this "
                f"node's `spec` dependency.\n\n"
                f"Write `{filename}` in the current directory, a section of "
                f"a larger blueprint document set aimed at an AI coding "
                f"agent that will generate source code directly from it. "
                f"It must contain exactly these sections, in this order, "
                f"each derived from the actual content of spec.json rather "
                f"than generic boilerplate:\n\n"
                f"{section_list}\n\n"
                f"Be concrete and specific: name real files/modules, real "
                f"field names and types for data models, real endpoint "
                f"paths and payloads for interfaces, real function/class "
                f"names for algorithms and logic — enough detail that no "
                f"further product decisions are needed to start "
                f"implementing this part of the system.\n\n"
                + others_note
                + note
            ),
        )

        fatass.free(
            silent=True,
            model="sonnet",
            tools="Read,Write,Edit,Glob,Grep",
            readable=[spec],
            prompt=(
                f"Read `{filename}` in the current directory, which you (or "
                f"a prior step) just wrote — and `spec.json` in the "
                f"readable directory for this node's `spec` dependency.\n\n"
                f"Verify `{filename}` against spec.json section by section: "
                f"every requirement, constraint, or component relevant to "
                f"this file's declared sections "
                f"({', '.join(s['title'] for s in sections)}) must be "
                f"reflected concretely, and nothing in the file may "
                f"contradict spec.json. Check for ambiguity or gaps that "
                f"would leave a coding agent guessing (e.g. missing field "
                f"types, unspecified error cases, vague algorithm "
                f"descriptions) and for generic filler that isn't actually "
                f"derived from the spec.\n\n"
                f"Edit `{filename}` directly to fix anything you find. If "
                f"it already fully satisfies this, leave it unchanged — do "
                f"not rewrite for style alone."
            ),
        )

    if len(files) > 1:
        all_files = ", ".join(filenames)
        fatass.free(
            silent=True,
            model="sonnet",
            tools="Read,Write,Edit,Glob,Grep",
            readable=[spec],
            prompt=(
                f"Read every one of these blueprint files in the current "
                f"directory: {all_files}. Also read `spec.json` in the "
                f"readable directory for this node's `spec` dependency.\n\n"
                f"Do a final cross-file consistency pass across the whole "
                f"blueprint document set: check that names, data models, "
                f"interfaces, and terminology agree everywhere they're "
                f"referenced across files (e.g. a field described one way "
                f"in the data model file must match how it's used in an "
                f"interface or component file elsewhere); check that "
                f"cross-references between files point to things that "
                f"actually exist in the target file; check that nothing in "
                f"spec.json was dropped or contradicted across the set as a "
                f"whole.\n\n"
                f"Edit whichever files need fixing to resolve any "
                f"inconsistencies you find. If everything already agrees, "
                f"leave the files unchanged."
            ),
        )
