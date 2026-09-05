from .profs_search_result import ProfsSearchResult as ProfsSearchResultNode


def count() -> int:
    root = ProfsSearchResultNode()._assets_dir()
    total_chars = 0
    total_words = 0
    for path in root.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            total_chars += len(text)
            total_words += len(text.split())
    total_tokens = total_chars // 4
    print(f"char count: {total_chars}")
    print(f"word count: {total_words}")
    print(f"token count: {total_tokens}")
    return total_tokens
