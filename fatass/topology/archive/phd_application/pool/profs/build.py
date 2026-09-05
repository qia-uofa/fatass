import csv
import re

import fatass
from .profs import Profs as ProfCandidates
from fatass.topology.archive.phd_application.pool.unis import Unis as UniCandidates


FIELDNAMES = ["name", "department", "program", "research_area", "faculty_page", "email"]
TIMESTAMP_RE = re.compile(r"^(\d{8}_\d{6})\.csv$")


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def _is_complete(path):
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as fh:
        return len(list(csv.DictReader(fh))) > 0


def verify_professors(professors: list, uni_name: str) -> list:
    verified = []
    total_profs = len(professors)
    for j, prof in enumerate(professors, start=1):
        prof_name = prof.get("name", "?")
        print(f"build(prof_Candidates): verifying professor [{j}/{total_profs}] {prof_name} ({uni_name})...")
        checked = fatass.free(
            readable=[],
            silent=True,
            permission_mode="bypassPermissions",
            model="haiku",
            effort="low",
            tools="Write,WebSearch,WebFetch",
            returns=dict,
            prompt=(
                f"Draft record for a professor, to be minimally verified:\n"
                f"{prof}\n\n"
                f"They are claimed to be at {uni_name}. Do ONE quick web search to "
                f"sanity-check this record and correct any fields you can -- don't do "
                f"deep research, a search plus maybe one page fetch is enough. If the "
                f"professor doesn't look real or isn't actually at {uni_name}, still return "
                f"your best-guess corrected record rather than dropping it -- a later "
                f"step handles final verification, this pass is just a quick sanity "
                f"check, not the source of truth.\n\n"
                f"Return a single JSON object with exactly these keys: 'name', "
                f"'department', 'program', 'research_area', 'faculty_page' (empty "
                f"string if unsure), 'email' (empty string if unsure)."
            ),
        )
        verified.append(checked)
    return verified


def _write_professors(out_path, professors):
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for prof in professors:
            writer.writerow({k: prof.get(k, "") for k in FIELDNAMES})


def build(uni_candidates: UniCandidates, n: int = 8):
    print("build(prof_Candidates): locating latest uni_candidates CSV list...")
    candidates_dir = uni_candidates._assets_dir()
    timestamped = []
    for f in candidates_dir.glob("*.csv"):
        m = TIMESTAMP_RE.match(f.name)
        if m:
            timestamped.append((m.group(1), f))
    if not timestamped:
        raise FileNotFoundError(
            f"No timestamped uni list (YYYYMMDD_HHMMSS.csv) found in {candidates_dir}"
        )
    timestamp, latest_csv = max(timestamped, key=lambda item: item[0])
    print(f"build(prof_Candidates): using uni list {latest_csv.name}")

    with latest_csv.open(newline="", encoding="utf-8") as fh:
        universities = list(csv.DictReader(fh))

    node = ProfCandidates()
    out_dir = node._assets_dir() / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"build(prof_Candidates): writing results to {out_dir}")

    total_unis = len(universities)
    rank_width = len(str(total_unis))
    for i, uni in enumerate(universities, start=1):
        name = (uni.get("university") or "").strip()
        if not name:
            continue

        filename = f"{i:0{rank_width}d}_{_sanitize_filename(name)}.csv"
        out_path = out_dir / filename

        if _is_complete(out_path):
            print(f"build(prof_Candidates): [{i}/{total_unis}] {out_path.name} already complete, skipping")
            continue

        print(f"build(prof_Candidates): [{i}/{total_unis}] quick web search for ML/AI/CV/LLM faculty at {name}...")
        professors = fatass.free(
            readable=[],
            silent=True,
            permission_mode="bypassPermissions",
            model="haiku",
            effort="low",
            tools="Write,WebSearch,WebFetch",
            returns=list,
            prompt=(
                f"University: {name} (city: {uni.get('city', '')}, "
                f"state: {uni.get('state', '')}, type: {uni.get('type', '')}, "
                f"website: {uni.get('website', '')}).\n\n"
                f"Do ONE quick web search (e.g. \"{name} machine learning faculty\") and "
                f"skim the top results -- do not do multi-step deep research or fetch many "
                f"pages. From that plus general knowledge, name as many professors at "
                f"{name} as you can find who work in machine learning, AI, computer "
                f"vision, and/or LLMs, up to a maximum of {n} -- fewer is fine if "
                f"that's genuinely all you can find, don't pad the list. Any department "
                f"counts, not just CS. This is a fast "
                f"first-pass draft that a later step will verify and correct, so "
                f"approximate/best-guess answers are fine and expected -- don't spend "
                f"effort double-checking or fetching more than a couple of pages.\n\n"
                f"Return a JSON list of objects, one per professor, each with exactly "
                f"these keys: 'name', 'department', 'program', 'research_area' (short "
                f"phrase, e.g. 'computer vision' or 'LLMs / NLP'), 'faculty_page' (empty "
                f"string if unsure), 'email' (empty string if unsure)."
            ),
        )

        print(f"build(prof_Candidates): [{i}/{total_unis}] writing {out_path.name} ({len(professors)} professors)")
        _write_professors(out_path, professors)

    print("build(prof_Candidates): done.")
