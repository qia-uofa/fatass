from fatass.topology.examples.portfolio.projects import Projects as Projects


def purge_summary(projects: Projects, i: int = -1):
    print("purge_summary: starting")
    projects = Projects()
    indices = range(Projects.length()) if i == -1 else [i]
    for i in indices:
        item = projects[i]
        print(f"purge_summary: project {i} purging summary")
        item.summary.purge_self()

    print("purge_summary: done")
