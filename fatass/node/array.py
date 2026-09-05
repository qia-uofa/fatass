import itertools
from pathlib import Path

from ..errors import TopologyValidationError
from .node import Node


class Array(Node):
    """A `Node` whose entire content is a fixed-shape grid of files, one
    per index in `range(DIM[0]) x range(DIM[1]) x ...` — declared as a
    class attribute on the concrete node subclass, e.g.
    `class Foo(fatass.ArrayTxt): DIM = (2, 2, 2)`. Never a directory of
    otherwise-arbitrary content — `write()` is the only sanctioned way to
    populate it (see the "transform convention" note in CLAUDE.md)."""

    EXT: str = ""
    DIM: tuple[int, ...] = ()
    FIELDS: tuple[str, ...] = ()

    @classmethod
    def _indices(cls) -> "itertools.product[tuple[int, ...]]":
        return itertools.product(*(range(d) for d in cls.DIM))

    @classmethod
    def _validate_index(cls, index: tuple[int, ...]) -> None:
        if len(index) != len(cls.DIM):
            raise TopologyValidationError(
                f"{cls._topology_path()}: index {list(index)} has "
                f"{len(index)} dimensions, expected {len(cls.DIM)} "
                f"(DIM={list(cls.DIM)})"
            )
        for axis, (i, d) in enumerate(zip(index, cls.DIM)):
            if not (0 <= i < d):
                raise TopologyValidationError(
                    f"{cls._topology_path()}: index {list(index)} out of "
                    f"range on axis {axis} (DIM={list(cls.DIM)})"
                )

    @classmethod
    def _file_name(cls, index: tuple[int, ...]) -> str:
        return "_" + "_".join(str(i) for i in index) + cls.EXT

    @classmethod
    def _file_path(cls, index: tuple[int, ...]) -> Path:
        cls._validate_index(index)
        return cls._assets_dir() / cls._file_name(index)

    @classmethod
    def on_created(cls) -> None:
        cls._assets_dir().mkdir(parents=True, exist_ok=True)
        header = ",".join(cls.FIELDS) + "\n" if cls.FIELDS else ""
        for index in cls._indices():
            path = cls._file_path(index)
            if not path.exists():
                path.write_text(header, encoding="utf-8")

    @classmethod
    def purge_self(cls) -> int:
        """Clears every file that currently exists, in place, skipping
        (not creating) any that's missing. Never raises."""
        cleared = 0
        for index in cls._indices():
            path = cls._file_path(index)
            if path.is_file():
                path.write_bytes(b"")
                cleared += 1
        return cleared

    @classmethod
    def write(cls, index: "list[int] | tuple[int, ...]", content: str) -> None:
        """Writes `content` to the file at `index`, creating it (and this
        node's home/ directory) first if either doesn't exist yet."""
        path = cls._file_path(tuple(index))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @classmethod
    def _sys_prompt(cls) -> str:
        """Built fresh per class rather than a shared constant, so it
        reflects this concrete subclass's own `EXT`/`DIM` instead of
        generic placeholder text. A typed subclass with its own extra
        convention (e.g. ArrayCsv's fixed header row) overrides this and
        appends to it via `super()._sys_prompt()`, rather than duplicating
        this base text — see ArrayCsv below."""
        name_pattern = f"_<i>_<j>_...{cls.EXT}"
        shape = (
            " x ".join(f"range({d})" for d in cls.DIM)
            if cls.DIM
            else "range(DIM[0]) x range(DIM[1]) x ..."
        )
        return (
            f"## `{cls.__name__}` (an `Array`) — a node that manages a fixed-shape grid of files\n\n"
            f"This node's entire content is {'*'.join(str(d) for d in cls.DIM) or 'DIM[0] * DIM[1] * ...'} "
            f"files with no further structure, named `{name_pattern}`, directly under "
            f"its own home/ directory, one per index in {shape} — never a directory "
            f"of otherwise-arbitrary agent-written content.\n\n"
            f"A transform that populates this node must NOT let `fatass.free(...)` "
            f"write into this node's home/ directory directly (e.g. via `writable=` "
            f"or by just letting the agent edit files there). Instead, capture each "
            f"result with `returns=str` and call `NodeClass.write([i, j, ...], "
            f"result)` yourself — `write()` creates the file if it doesn't exist "
            f"yet, so this is safe to call unconditionally."
        )

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return cls._sys_prompt()


class ArrayTxt(Array):
    EXT = ".txt"


class ArrayPdf(Array):
    EXT = ".pdf"


class ArrayMd(Array):
    EXT = ".md"


class ArrayJson(Array):
    EXT = ".json"


class ArrayHtml(Array):
    EXT = ".html"


class ArrayCsv(Array):
    EXT = ".csv"
    FIELDS: tuple[str, ...] = ()

    @classmethod
    def _sys_prompt(cls) -> str:
        text = super()._sys_prompt()
        if not cls.FIELDS:
            return text
        return (
            f"{text}\n\n"
            f"### `{cls.__name__}` is also an `ArrayCsv` — each file's header row is fixed\n\n"
            f"Each file's header row is fixed: `{','.join(cls.FIELDS)}` — "
            f"`write()` replaces that file wholesale, so include that header "
            f"line yourself in whatever content you pass it if you want it "
            f"preserved."
        )
