import fatass
from fatass.topology.examples.portfolio.cv.checkpoints import Checkpoints as Checkpoints
from fatass.topology.examples.portfolio.projects import Projects as Projects


def fetch(checkpoints: Checkpoints):
    print("fetch: reading already-saved project titles")
    existing_titles = []
    for i in range(Projects.length()):
        info_cls = Projects()[i].info
        title = info_cls._file_path("titile").read_text(encoding="utf-8").strip()
        if title:
            existing_titles.append(title)

    print("fetch: reading newest checkpoint's CV pdf")
    newest_checkpoint = checkpoints[Checkpoints.length() - 1]
    cv_file = newest_checkpoint.file

    print("fetch: extracting projects from the CV")
    new_projects = fatass.free(
        readable=[cv_file],
        returns=list,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt=(
            "The readable directory holds the newest checkpoint of a CV, as a "
            "PDF file. Read it and identify every distinct project mentioned in "
            "it. These project titles are already recorded and must be skipped — "
            "treat a project as already recorded if it clearly refers to the "
            "same project even when worded differently (paraphrased, "
            "abbreviated, reordered, or otherwise not an exact string match): "
            f"{', '.join(existing_titles) if existing_titles else '(none yet)'}. "
            "Report back a JSON array of objects, one per project that is NOT "
            "already in that list, each with exactly these keys: 'titile' "
            "(the project's title), 'role', 'start_time', 'end_time', and "
            "'context' (a brief description of the project). Use an empty "
            "string for any field you can't determine from the CV. If every "
            "project in the CV is already recorded, report an empty array."
        ),
    )

    if not isinstance(new_projects, list):
        new_projects = []

    print(f"fetch: found {len(new_projects)} new project(s)")
    for project in new_projects:
        if not isinstance(project, dict):
            continue
        Projects.extend()
        index = Projects.length() - 1
        info_cls = Projects()[index].info
        for field in info_cls.FIELDS:
            value = project.get(field, "")
            print(f"fetch: writing project {index} field '{field}'")
            info_cls.write(field, value)

    print("fetch: done")
