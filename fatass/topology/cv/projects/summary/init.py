import fatass
from fatass.topology.cv.projects.source import Source as Source
from .summary import Summary


def init(source: Source):
    print("init: summarizing project source")
    result = fatass.free(
        readable=[source],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        prompt=(
            "source depends on node `cv.projects.source` — read the project "
            "source files in its readable directory and write a brief summary "
            "of the project (a few sentences) as markdown."
        ),
    )
    print("init: writing summary")
    Summary.write(result)
