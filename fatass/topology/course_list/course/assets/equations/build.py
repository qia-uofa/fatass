import fatass
from fatass.topology.course_list.course.assets.equations import Equations as Equations
from fatass.topology.course_list.course.materials.lectures import Lectures as Lectures


EQUATION_FORMAT = """Each equation entry must be a JSON object with these fields:
- "name": short label/name for the equation
- "latex": the equation itself, in LaTeX (no surrounding $ delimiters)
- "explanation": a few sentences on what the equation means and is used for
- "variables": a list of {"symbol": ..., "meaning": ...} objects, one per symbol used
"""


def _format_equation(eq: dict) -> str:
    lines = [
        f"# {eq.get('name', 'Equation')}",
        "",
        f"$${eq.get('latex', '')}$$",
        "",
        eq.get("explanation", ""),
        "",
        "## Variables",
        "",
    ]
    for v in eq.get("variables", []):
        lines.append(f"- ${v.get('symbol', '')}$: {v.get('meaning', '')}")
    return "\n".join(lines)


def build(lectures: Lectures):
    print("build@course.assets.equations: reading all materials for context")
    context = fatass.free(
        readable=[lectures],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt=(
            "Dependency `lectures` (node `course.materials.lectures`) has a readable "
            "directory whose internal structure is not fixed — explore it fully with "
            "Glob/Read before assuming any particular layout (it may hold notes, slides, "
            "or PDFs, in any arrangement).\n\n"
            "Read through ALL of it and write a concise (a few paragraphs) context "
            "summary covering the material's overall themes, notation conventions, and "
            "how it's organized (e.g. file order/topics), so that a later pass extracting "
            "equations file-by-file can stay consistent in naming and notation."
        ),
    )
    print("build@course.assets.equations: context gathered")

    lectures_dir = lectures._assets_dir()
    files = sorted(p for p in lectures_dir.rglob("*") if p.is_file())

    equations_node = Equations()
    extracted_so_far = "(none yet)"

    for path in files:
        rel = path.relative_to(lectures_dir)
        print(f"build@course.assets.equations: extracting equations from {rel}")
        found = fatass.free(
            readable=[lectures],
            returns=list,
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            effort="low",
            tools="Read,Write,Edit,Glob,Grep,Bash",
            prompt=(
                f"Course context (from all materials):\n{context}\n\n"
                "Equations already extracted from earlier material in this pass — do "
                f"not repeat any of these:\n{extracted_so_far}\n\n"
                f"Now focus only on the file `{rel}` inside dependency `lectures`'s "
                "readable directory. Find every distinct mathematical equation or "
                "formula presented in it, skipping any already listed above. Report a "
                f"JSON list, one object per equation, in this format:\n{EQUATION_FORMAT}\n"
                "Report an empty list if this file has no equations."
            ),
        )
        for eq in found:
            equations_node.extend()
            item = equations_node[equations_node.length() - 1]
            (item._assets_dir() / "_.md").write_text(
                _format_equation(eq), encoding="utf-8"
            )
            extracted_so_far += f"\n- {eq.get('name', '')}: {eq.get('latex', '')}"

    print("build@course.assets.equations: done")
