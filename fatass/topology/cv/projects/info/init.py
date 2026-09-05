import fatass
from fatass.topology.cv.projects.source import Source as Source
from fatass.topology.cv.projects.info import Info as Info


def init(source: Source):
    print("init: extracting fields from source")
    result = fatass.free(
        readable=[source],
        returns=dict,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        prompt=(
            "source depends on node `cv.projects.source` — read the files in its "
            "readable directory and extract values for each of these fields: "
            f"{', '.join(Info.FIELDS)}. "
            "Report back a JSON object mapping each field name to its extracted "
            "value as plain text. If a field's value cannot be recognized from the "
            "source, use an empty string \"\" for that field."
        ),
    )
    for field in Info.FIELDS:
        value = result.get(field, "") if isinstance(result, dict) else ""
        print(f"init: writing '{field}'")
        Info.write(field, value)
