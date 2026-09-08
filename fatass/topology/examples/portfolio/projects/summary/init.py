import fatass
from fatass.topology.examples.portfolio.projects.source import Source as Source
from fatass.topology.examples.portfolio.projects.info import Info as Info


def _source_has_content(source_dir):
    if not source_dir.exists():
        return False
    return any(p.is_file() and p.stat().st_size > 0 for p in source_dir.rglob("*"))


def init(source: Source, info: Info, word_count: int = 500):
    me = fatass.current_node()
    source_dir = source._assets_dir()

    if _source_has_content(source_dir):
        print("init: summarizing project source")
        result = fatass.free(
            readable=[source],
            returns=str,
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            tools="Read,Write,Edit,Glob,Grep,Bash",
            prompt=(
                "The readable directory holds this project's source material — read "
                f"it and report back a summary of the project (about {word_count} "
                "words) as markdown. Your returned result must be the summary text "
                "itself, not a description of what you did — and do not write it to "
                "any file yourself; the caller will write your returned text to the "
                "destination file."
            ),
        )
    else:
        print("init: source is empty, inferring summary from sibling info fields")
        info_dir = info._assets_dir()
        info_lines = ""
        if info_dir.is_dir():
            info_lines = "\n".join(
                f"{f.name}: {f.read_text(encoding='utf-8').strip()}"
                for f in sorted(info_dir.iterdir())
                if f.is_file() and f.read_text(encoding="utf-8").strip()
            )
        result = fatass.free(
            readable=[],
            returns=str,
            silent=True,
            permission_mode="bypassPermissions",
            model="sonnet",
            tools="Read,Write,Edit,Glob,Grep",
            prompt=(
                "Here is what is known about a project, as field: value "
                f"pairs:\n{info_lines if info_lines else '(no fields known)'}\n"
                f"Infer and report back a brief summary of the project (about "
                f"{word_count} words, or shorter if little is known) as "
                "markdown, based only on this information. Your returned "
                "result must be the summary text itself, not a description of "
                "what you did."
            ),
        )
    print("init: writing summary")
    me.write(result)
