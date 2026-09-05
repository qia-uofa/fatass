from pathlib import Path

from .node import Node


class Single(Node):
    """A `Node` whose entire content is one fixed-name file: `_` for the
    bare class, `_<EXT>` for a subclass that sets `EXT` (e.g. `SingleTxt`
    -> `_.txt`). Never a directory of otherwise-arbitrary content —
    `write()` is the only sanctioned way to populate it (see the
    "transform convention" note in CLAUDE.md)."""

    EXT: str = ""
    FIELDS: tuple[str, ...] = ()

    @classmethod
    def _file_name(cls) -> str:
        return f"_{cls.EXT}"

    @classmethod
    def _file_path(cls) -> Path:
        return cls._assets_dir() / cls._file_name()

    @classmethod
    def on_created(cls) -> None:
        path = cls._file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(",".join(cls.FIELDS) + "\n" if cls.FIELDS else "", encoding="utf-8")

    @classmethod
    def purge_self(cls) -> int:
        """Clears the file in place instead of deleting it. A no-op
        (returns 0) if the file doesn't currently exist — never raises."""
        path = cls._file_path()
        if not path.is_file():
            return 0
        path.write_bytes(b"")
        return 1

    @classmethod
    def write(cls, content: str) -> None:
        """Writes `content` straight to the managed file, creating it
        (and this node's home/ directory) first if either doesn't exist
        yet."""
        path = cls._file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @classmethod
    def _sys_prompt(cls) -> str:
        """Built fresh per class rather than a shared constant, so it
        reflects this concrete subclass's own `EXT` instead of generic
        placeholder text. A typed subclass with its own extra convention
        (e.g. SingleCsv's fixed header row) overrides this and appends to
        it via `super()._sys_prompt()`, rather than duplicating this base
        text — see SingleCsv below."""
        file_name = cls._file_name() or "_"
        return (
            f"## `{cls.__name__}` (a `Single`) — a node that manages exactly one fixed-name file\n\n"
            f"This node's entire content is one file, named `{file_name}`, directly "
            f"under its own home/ directory — never a directory of arbitrary "
            f"agent-written content.\n\n"
            f"A transform that populates this node must NOT let `fatass.free(...)` "
            f"write into this node's home/ directory directly (e.g. via `writable=` "
            f"or by just letting the agent edit files there). Instead, capture the "
            f"agent's result with `returns=str` and call `NodeClass.write(result)` "
            f"yourself — `write()` creates the file if it doesn't exist yet, so this "
            f"is safe to call unconditionally."
        )

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return cls._sys_prompt()


class SingleTxt(Single):
    EXT = ".txt"


class SinglePdf(Single):
    EXT = ".pdf"


class SingleMd(Single):
    EXT = ".md"


class SingleJson(Single):
    EXT = ".json"


class SingleHtml(Single):
    EXT = ".html"


class SingleCsv(Single):
    EXT = ".csv"
    FIELDS: tuple[str, ...] = ()

    @classmethod
    def _sys_prompt(cls) -> str:
        text = super()._sys_prompt()
        if not cls.FIELDS:
            return text
        return (
            f"{text}\n\n"
            f"### `{cls.__name__}` is also a `SingleCsv` — its header row is fixed\n\n"
            f"Its header row is fixed: `{','.join(cls.FIELDS)}` — `write()` "
            f"replaces the whole file, so include that header line yourself in "
            f"whatever content you pass it if you want it preserved."
        )
