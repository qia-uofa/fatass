from .profs_context_window import ProfsContextWindow
from fatass.topology.phd_application.pool.profs_search_result import ProfsSearchResult as ProfsSearchResult


def build(profs_search_result: ProfsSearchResult):
    print("profs_context_window.build: starting")
    src_dir = profs_search_result._assets_dir()
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())

    parts = []
    for path in files:
        rel = path.relative_to(src_dir)
        print(f"profs_context_window.build: reading {rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"profs_context_window.build: skipping non-text file {rel}")
            continue
        parts.append(f"===== {rel} =====\n{text}")

    combined = "\n\n".join(parts)

    out_path = ProfsContextWindow()._assets_dir() / "_.txt"
    print(f"profs_context_window.build: writing {out_path}")
    out_path.write_text(combined, encoding="utf-8")
    print("profs_context_window.build: done")
