import base64
import csv
import html
import re
import urllib.parse
import urllib.request

from .profs_search_result import ProfsSearchResult as ProfsSearchResultNode
from fatass.topology.phd_application.pool.profs import Profs as PoolProfs

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
MAX_RESULTS_PER_PROF = 2


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _html_to_text(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _search_urls_duckduckgo(query: str, max_results: int) -> list:
    search_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    page = _fetch(search_url)

    urls = []
    for link in re.findall(r'class="result__a"[^>]*href="([^"]+)"', page):
        parsed = urllib.parse.urlparse(link)
        real = urllib.parse.parse_qs(parsed.query).get("uddg", [link])[0]
        real = urllib.parse.unquote(real)
        if real not in urls:
            urls.append(real)
        if len(urls) >= max_results:
            break
    return urls


def _unwrap_bing_redirect(link: str) -> str:
    parsed = urllib.parse.urlparse(link)
    u = urllib.parse.parse_qs(parsed.query).get("u", [None])[0]
    if u and u.startswith("a1"):
        b64 = u[2:]
        padded = b64 + "=" * (-len(b64) % 4)
        try:
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        except Exception:
            pass
    return link


def _search_urls_bing(query: str, max_results: int) -> list:
    search_url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    page = _fetch(search_url)

    urls = []
    for link in re.findall(r'<li class="b_algo"[^>]*>.*?<a[^>]*href="([^"]+)"', page, flags=re.S):
        real = _unwrap_bing_redirect(link)
        if real not in urls:
            urls.append(real)
        if len(urls) >= max_results:
            break
    return urls


def _search_urls(query: str, max_results: int = MAX_RESULTS_PER_PROF) -> list:
    for engine_name, engine in (("duckduckgo", _search_urls_duckduckgo), ("bing", _search_urls_bing)):
        try:
            urls = engine(query, max_results)
        except Exception as exc:
            print(f"build(profs_search_result): {engine_name} search failed for {query!r}: {exc}")
            continue
        if urls:
            return urls
    return []


def build(profs: PoolProfs):
    print("build(profs_search_result): locating latest prof candidates directory...")
    candidates_dir = profs._assets_dir()
    timestamped_dirs = [d for d in candidates_dir.iterdir() if d.is_dir()]
    if not timestamped_dirs:
        raise FileNotFoundError(f"No timestamped prof-candidates directory found in {candidates_dir}")
    latest_dir = max(timestamped_dirs, key=lambda d: d.name)
    print(f"build(profs_search_result): using prof candidates {latest_dir.name}")

    out_root = ProfsSearchResultNode()._assets_dir()

    uni_files = []
    for uni_file in sorted(latest_dir.glob("*.csv")):
        m = re.match(r"^(\d+)_(.+)\.csv$", uni_file.name)
        if not m:
            continue
        rank, uni_name = m.group(1), m.group(2)
        with uni_file.open(newline="", encoding="utf-8") as fh:
            professors = list(csv.DictReader(fh))
        uni_files.append((rank, uni_name, professors))

    total_profs = sum(len(professors) for _, _, professors in uni_files)

    i = 0
    for rank, uni_name, professors in uni_files:
        uni_dir = out_root / f"{rank}-{_sanitize_filename(uni_name)}"

        for prof in professors:
            prof_name = (prof.get("name") or "").strip()
            if not prof_name:
                continue
            i += 1
            prof_dir = uni_dir / _sanitize_filename(prof_name)
            if prof_dir.is_dir() and any(prof_dir.glob("file*.txt")):
                print(f"build(profs_search_result): ({i}/{total_profs}) skipping {prof_name} ({uni_name}), already fetched")
                continue

            print(f"build(profs_search_result): ({i}/{total_profs}) searching for {prof_name} ({uni_name})...")
            urls = _search_urls(f"{uni_name} {prof_name}")
            if not urls:
                print(f"build(profs_search_result): no results for {prof_name} ({uni_name})")
                continue

            prof_dir.mkdir(parents=True, exist_ok=True)
            for url_idx, url in enumerate(urls, start=1):
                out_path = prof_dir / f"file{url_idx}.txt"
                if out_path.exists():
                    continue
                try:
                    raw = _fetch(url)
                except Exception as exc:
                    print(f"build(profs_search_result): failed to fetch {url}: {exc}")
                    continue
                out_path.write_text(f"{url}\n\n{_html_to_text(raw)}", encoding="utf-8")
                print(f"build(profs_search_result): wrote {out_path}")

    print("build(profs_search_result): done.")
