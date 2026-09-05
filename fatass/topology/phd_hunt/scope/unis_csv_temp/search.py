import fatass
from fatass.topology.phd_hunt.scope.unis_csv_temp import UnisCsvTemp as UnisCsv


def search():
    print("search: researching universities...")
    header = ",".join(UnisCsv.FIELDS)
    result = fatass.free(
        readable=[],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        prompt=(
            f"Search the web for US universities' {UnisCsv.faculty} departments/faculties, "
            f"ranked from #{UnisCsv.rank_top} to #{UnisCsv.rank_bot} (inclusive) on a reputable "
            f"overall or subject-specific ranking (e.g. USNews, QS, or a well-known CS "
            f"ranking such as CSRankings). For each university in that rank range, gather "
            f"these fields: {', '.join(UnisCsv.FIELDS)} -- 'rank' is its rank in the ranking "
            f"you used, 'name' is the university's name, 'state' is the US state it's "
            f"located in, 'url' is the {UnisCsv.faculty} department/faculty's own homepage "
            f"URL, and 'people_url' is a URL to a page listing that department's faculty "
            f"members (e.g. a directory or people page). Report your result (via returns) as the CSV body only "
            f"-- one line per university, comma-separated in exactly this field order: "
            f"{header}. Do not include the header row; do not wrap fields in quotes unless "
            f"a field itself contains a comma."
        ),
    )
    print("search: writing results to _.csv")
    UnisCsv.write(header + "\n" + result.strip() + "\n")
    print("search: done")
