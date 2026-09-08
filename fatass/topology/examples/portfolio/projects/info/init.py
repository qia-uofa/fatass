import fatass
from fatass.topology.examples.portfolio.projects.source import Source as Source


def init(source: Source):
    me = fatass.current_node()

    print("init: extracting fields from source")
    result = fatass.free(
        readable=[source],
        returns=dict,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,Bash",
        prompt=(
            "The readable directory holds this project's source material — read "
            "the files in it and extract values for each of these fields: "
            f"{', '.join(me.FIELDS)}. "
            "Report back a JSON object mapping each field name to its extracted "
            "value as plain text. If a field's value cannot be recognized from the "
            "source, use an empty string \"\" for that field."
        ),
    )
    for field in me.FIELDS:
        value = result.get(field, "") if isinstance(result, dict) else ""
        print(f"init: writing '{field}'")
        me.write(field, value)
