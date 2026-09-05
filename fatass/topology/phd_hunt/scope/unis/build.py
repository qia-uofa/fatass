import csv
import json
import urllib.request

import fatass
from fatass.topology.phd_hunt.scope.unis_csv_temp import UnisCsvTemp as UnisCsv
from fatass.topology.phd_hunt.scope.unis import Unis as Unis
from fatass.topology.phd_hunt.scope.unis.peoples.information import Information as Information
from fatass.topology.phd_hunt.scope.unis.peoples.homepage import Homepage as Homepage

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; fatass-phd-hunt/1.0)"}
_MAX_LISTING_CHARS = 200_000

# Hardcoded schema for peoples[j].information's JSON content.
_PERSON_FIELDS = ("name", "title", "email", "homepage_url")

_NAME_MARKER = "name.txt"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")


# `peoples_cls()[i].information`/`.homepage` (chained attribute access on a
# `_ChainItem` of a *dynamically derived* Chain subclass) crashes: the
# nested dynamic subclass `_ChainItem.__getattr__` builds internally doesn't
# preserve `__module__`, so its `_topology_path()` raises "not defined under
# fatass.topology". Sidestep that nested resolution entirely by pointing a
# fresh subclass of the real schema class straight at the item's directory,
# computed via `_depth_dir` (the same primitive `_ChainItem` itself uses).
def _bound(schema_cls, target_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    return type(schema_cls.__name__, (schema_cls,), {"_assets_dir": classmethod(lambda cls, _d=target_dir: _d)})


def _existing_uni_names(unis: Unis) -> set:
    names = set()
    for i in range(Unis.length()):
        marker = unis[i]._assets_dir() / _NAME_MARKER
        if marker.is_file():
            names.add(marker.read_text(encoding="utf-8").strip())
    return names


def _existing_person_keys(peoples_cls) -> set:
    keys = set()
    for i in range(peoples_cls.length()):
        info_path = _bound(Information, peoples_cls._depth_dir(i) / "information")._file_path()
        if not info_path.is_file():
            continue
        try:
            data = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        keys.add((data.get("name", ""), data.get("homepage_url", "")))
    return keys


def build(unis_csv: UnisCsv, rank_top: int = 1, rank_bot: int = 9999):
    lo = max(rank_top, unis_csv.rank_top)
    hi = min(rank_bot, unis_csv.rank_bot)
    print(f"Reading unis_csv, keeping ranks {lo}..{hi}")

    with unis_csv._file_path().open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if lo > hi:
        raise ValueError(
            f"empty rank range: requested {rank_top}..{rank_bot} doesn't "
            f"overlap unis_csv's own {unis_csv.rank_top}..{unis_csv.rank_bot}"
        )

    unis = Unis()
    already_present = _existing_uni_names(unis)

    matched = 0
    fetch_failures = []

    for row in rows:
        rank = int(row["rank"])
        if not (lo <= rank <= hi):
            continue
        matched += 1

        name = row["name"]
        if name in already_present:
            print(f"Skipping {name}: already present in unis")
            continue

        people_url = row["people_url"]
        print(f"Fetching people listing for {name}: {people_url}")
        try:
            listing_html = _fetch(people_url)
        except Exception as exc:
            print(f"  failed to fetch {people_url}: {exc}; skipping {name}")
            fetch_failures.append((name, people_url, str(exc)))
            continue

        people = fatass.free(
            readable=[],
            returns=list,
            silent=True,
            permission_mode="bypassPermissions",
            tools="Read,Write,Edit,Glob,Grep",
            model="sonnet",
            prompt=(
                f"Below is the raw HTML of the people/faculty listing page for "
                f"{name} ({people_url}). Extract every person listed on it and "
                f"report a JSON list, one object per person, with exactly these "
                f"fields: {list(_PERSON_FIELDS)!r} — \"name\" (str), \"title\" "
                f"(str, their listed position/role, \"\" if none), \"email\" "
                f"(str, \"\" if none), \"homepage_url\" (str, an absolute URL to "
                f"their personal homepage if one is linked, else \"\"). Report "
                f"only the JSON list, nothing else.\n\n"
                f"--- HTML START ---\n{listing_html[:_MAX_LISTING_CHARS]}\n--- HTML END ---"
            ),
        )

        print(f"  extracted {len(people)} people for {name}")
        Unis.extend()
        uni_item = unis[Unis.length() - 1]
        (uni_item._assets_dir() / _NAME_MARKER).write_text(name, encoding="utf-8")
        already_present.add(name)
        peoples_cls = uni_item.peoples

        existing_people = _existing_person_keys(peoples_cls)
        for person in people:
            info = {field: person.get(field, "") for field in _PERSON_FIELDS}
            key = (info["name"], info["homepage_url"])
            if key in existing_people:
                print(f"    skipping {info['name'] or '(unnamed)'}: already present")
                continue
            existing_people.add(key)

            peoples_cls.extend()
            person_dir = peoples_cls._depth_dir(peoples_cls.length() - 1)
            _bound(Information, person_dir / "information").write(json.dumps(info, indent=2))
            print(f"    added {info['name'] or '(unnamed)'}")

            homepage_url = info["homepage_url"]
            if homepage_url:
                try:
                    homepage_html = _fetch(homepage_url)
                except Exception as exc:
                    print(f"    failed to fetch homepage {homepage_url}: {exc}")
                    homepage_html = ""
                _bound(Homepage, person_dir / "homepage").write(homepage_html)

    if matched and len(fetch_failures) == matched:
        details = "; ".join(f"{name} ({url}): {err}" for name, url, err in fetch_failures)
        raise RuntimeError(
            f"all {matched} matched row(s) in ranks {lo}..{hi} failed to fetch "
            f"their people_url — nothing was added: {details}"
        )
