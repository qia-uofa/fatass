from fatass.topology.examples.portfolio.projects import Projects as Projects


def list(projects: Projects):
    projects = Projects()
    rows = []
    for i in range(Projects.length()):
        info_cls = projects[i].info
        rows.append(tuple(
            info_cls._file_path(field).read_text(encoding="utf-8").strip()
            for field in info_cls.FIELDS if field != 'context'
        ))

    if not rows:
        print("(no projects)")
        return

    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print(" | ".join(str(v).ljust(w) for v, w in zip(row, widths)))
