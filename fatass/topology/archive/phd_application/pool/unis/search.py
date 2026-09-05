import csv
from datetime import datetime

import fatass

from .unis import Unis as SearchResult


def search(n:int):
    print("start searching")
    universities = fatass.free(
        readable=[],
        returns=list,
        silent=False,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        prompt=f"""Go to https://csrankings.org — the most reliable CS
ranking for PhD-application purposes, since it ranks departments by counting
each faculty member's actual publications in top-tier CS venues over the
last 10 years, rather than by reputation survey. Use the site's default
"All Areas" aggregate view (do not switch to a single subarea), restrict the
region filter to "USA" (top-left region dropdown), and read off the
resulting ranked list of institutions in the order the site displays them —
that order is the ranking to use. Take the first {n} US institutions from
that list, and determine each one's full official name (e.g. "Massachusetts
Institute of Technology", not "MIT").

Return your final result as a JSON list of exactly {n} objects, ordered by
rank, each with the keys "rank" (an integer, 1-{n}), "university" (the
full official name), "city", "state" (the two-letter US postal
abbreviation), "type" ("Public" or "Private"), and "website" (the
university's official homepage URL).

Don't overthink, don't get too deep into searching.""",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = SearchResult._assets_dir() / f"{timestamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["rank", "university", "city", "state", "type", "website"],
        )
        writer.writeheader()
        writer.writerows(universities)
