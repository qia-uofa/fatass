import fatass
from fatass.topology.thesis.assets.equations import Equations as Equations

_CHECKS = {
    "notation": (
        "Check the equations for consistent notation and symbol usage: the same "
        "quantity should always be written with the same symbol, and the same symbol "
        "should always denote the same quantity."
    ),
    "definitions": (
        "Check that every symbol reused across more than one equation has a consistent "
        "definition everywhere it appears — same meaning, same domain/type, no symbol "
        "silently redefined partway through."
    ),
    "units": (
        "Check the equations for consistent units and dimensional conventions — every "
        "equation should be dimensionally consistent, and quantities shared across "
        "equations should use the same units throughout."
    ),
    "logical": (
        "Check the equations for logical consistency — no two equations should imply "
        "contradictory claims, and any equation presented as derived from another should "
        "actually follow from it."
    ),
}


def verify(equations: Equations):
    print("verify: checking equations in _.md for cross-consistency")
    out_dir = equations._assets_dir() / "_verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, instructions in _CHECKS.items():
        print(f"verify: running '{name}' check")
        report = fatass.free(
            readable=[equations],
            returns=str,
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            effort="low",
            tools="Read,Write,Edit,Glob,Grep",
            prompt=(
                "equations depends on node `thesis.assets.equations` — read `_.md` in its "
                "readable directory; it holds the thesis's collected equations. "
                f"{instructions} Report every inconsistency you find, quoting the specific "
                "equations involved; if everything is consistent, say so explicitly."
            ),
        )
        print(f"verify: writing _verify/{name}.md")
        (out_dir / f"{name}.md").write_text(report, encoding="utf-8")
    print("verify: done")
