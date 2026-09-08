import fatass
from fatass.topology.examples.portfolio.projects import Projects as Projects


def _source_has_content(source_dir):
    if not source_dir.exists():
        return False
    return any(p.is_file() and p.stat().st_size > 0 for p in source_dir.rglob("*"))


def audit_info(projects: Projects, i: int = -1):
    print("audit_info: starting")
    projects = Projects()
    indices = range(Projects.length()) if i == -1 else [i]
    for index in indices:
        item = projects[index]
        info_cls = item.info
        source_dir = item.source._assets_dir()

        missing_fields = [
            field
            for field in info_cls.FIELDS
            if not info_cls._file_path(field).read_text(encoding="utf-8").strip()
        ]
        if not missing_fields:
            print(f"audit_info: project {index} already complete, skipping")
            continue

        if not _source_has_content(source_dir):
            print(
                f"audit_info: project {index} source is empty, leaving info "
                f"fields {missing_fields} incomplete"
            )
            continue

        print(f"audit_info: project {index} filling info fields {missing_fields} from source")
        # Delegated to `info`'s own `init` transform, run scoped to this
        # item's index — running the fatass.free() call directly in this
        # loop instead would leave `fatass.current_node()` (and so
        # `free()`'s writable/cwd resolution) pinned to the whole,
        # unindexed `cv.projects` node for every iteration, since this
        # transform itself only ever gets `_current_node` set once, at
        # the top — silently mixing up which item's directory each
        # iteration's agent call actually reads/writes against. Routing
        # through `run_transform` re-enters `_call()`, which sets
        # `_current_node` freshly to *this* item's own depth-scoped class
        # (see `_ChainItem.__getattr__`, `info/init.py`).
        fatass.run_transform(f"cv.projects[{index}].info", "init", force=True)

    print("audit_info: done")
