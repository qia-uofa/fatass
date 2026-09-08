import fatass
from fatass.topology.examples.portfolio.projects import Projects as Projects


def _read_summary(summary_dir):
    if not summary_dir.exists():
        return ""
    md_files = sorted(summary_dir.glob("*.md"))
    if not md_files:
        return ""
    return md_files[0].read_text(encoding="utf-8").strip()


def audit_summary(projects: Projects, i: int = -1):
    print("audit_summary: starting")
    projects = Projects()
    indices = range(Projects.length()) if i == -1 else [i]
    for index in indices:
        item = projects[index]
        summary_text = _read_summary(item.summary._assets_dir())
        if summary_text:
            print(f"audit_summary: project {index} already complete, skipping")
            continue

        print(f"audit_summary: project {index} writing summary")
        # Delegated to `summary`'s own `init` transform (which already
        # handles both the "summarize from source" and "no source, infer
        # from info" cases — see summary/init.py), run scoped to this
        # item's index. Calling fatass.free() directly in this loop
        # instead would leave `fatass.current_node()` pinned to the
        # whole, unindexed `cv.projects` node for every iteration — this
        # transform's own `_current_node` is only ever set once, at the
        # top — so every iteration's agent call would share the same
        # (wrong) writable/cwd directory regardless of which item is
        # actually being processed. `run_transform` re-enters `_call()`,
        # which sets `_current_node` freshly to *this* item's own
        # depth-scoped class (see `_ChainItem.__getattr__`).
        fatass.run_transform(f"cv.projects[{index}].summary", "init", force=True)

    print("audit_summary: done")
