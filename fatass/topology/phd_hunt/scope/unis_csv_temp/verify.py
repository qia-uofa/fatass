import csv
import urllib.request

import fatass
from fatass.topology.phd_hunt.scope.unis_csv_temp import UnisCsvTemp as UnisCsv


def _is_alive(url: str) -> bool:
    if not url:
        return False
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception:
        return False


def verify(unis_csv: UnisCsv):
    print("verify: checking all urls in unis_csv")
    csv_path = unis_csv._assets_dir() / "_.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        for field in ("url", "people_url"):
            url = row.get(field, "")
            print(f"verify: checking {field} for {row.get('name')}: {url}")
            if _is_alive(url):
                continue
            print(f"verify: {field} for {row.get('name')} appears dead, researching replacement")
            replacement = fatass.free(
                readable=[],
                returns=str,
                silent=True,
                permission_mode="bypassPermissions",
                model="sonnet",
                effort="low",
                tools="WebSearch,WebFetch",
                prompt=(
                    f"The {field} URL `{url}` for university/department `{row.get('name')}` "
                    "appears to be dead (unreachable or erroring). Search the web to find the "
                    "current, correct URL for this page (the university's computer science "
                    "faculty page for `url`, or its people/faculty-listing page for "
                    "`people_url`). Reply with ONLY the corrected URL, nothing else. If no "
                    "working replacement can be found, reply with the single word `UNKNOWN`."
                ),
            )
            replacement = replacement.strip()
            print(f"verify: replacement for {field}/{row.get('name')}: {replacement}")
            if replacement and replacement != "UNKNOWN":
                row[field] = replacement

    lines = [",".join(UnisCsv.FIELDS)]
    for row in rows:
        lines.append(",".join(row.get(f, "") for f in UnisCsv.FIELDS))
    unis_csv.write("\n".join(lines) + "\n")
    print("verify: done checking urls")
