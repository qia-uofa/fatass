import fatass

from .profs_search_result_files import ProfsSearchResultFiles
from fatass.topology.archive.phd_application.pool.profs_search_result import ProfsSearchResult as ProfsSearchResult


def build(profs_search_result: ProfsSearchResult):
    src_dir = profs_search_result._assets_dir()
    dst_dir = ProfsSearchResultFiles()._assets_dir()

    link_files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    print(f"profs_search_result_files.build: found {len(link_files)} link file(s)")

    for i, link_path in enumerate(link_files):
        progress = f"({i + 1}/{len(link_files)})"
        rel_path = link_path.relative_to(src_dir)
        out_path = dst_dir / rel_path
        if out_path.exists():
            print(f"{progress} profs_search_result_files.build: {rel_path} already exists, skipping")
            continue

        link = link_path.read_text(encoding="utf-8").strip()
        print(f"{progress} profs_search_result_files.build: fetching {link}")

        result = fatass.free(
            readable=[],
            returns=str,
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            effort="low",
            tools="Read,Write,Edit,Glob,Grep,WebFetch",
            prompt=(
                f"Fetch the URL {link!r} and return its full readable page content "
                f"(the main text content of the page, not raw HTML markup). "
                f"Return only that content as plain text, nothing else."
            ),
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"{progress} profs_search_result_files.build: writing {rel_path}")
        out_path.write_text(result, encoding="utf-8")

    print("profs_search_result_files.build: done")
