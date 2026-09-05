from pathlib import Path

from ..errors import TopologyValidationError
from .node import Node


class Tuple(Node):
    """A `Node` whose entire content is a fixed set of named files, one
    per name in `FIELDS` — declared as a class attribute on the concrete
    node subclass, e.g. `class Foo(fatass.Tuple): FIELDS = ("field1",
    "field2")`. Unlike `Array`'s `_<i>_<j>_...` naming, each file is
    named exactly after its field — no prefix, no extension. Never a
    directory of otherwise-arbitrary content — `write()` is the only
    sanctioned way to populate it (see the "transform convention" note in
    CLAUDE.md)."""

    FIELDS: tuple[str, ...] = ()

    @classmethod
    def _validate_field(cls, field: str) -> None:
        if field not in cls.FIELDS:
            raise TopologyValidationError(
                f"{cls._topology_path()}: no field {field!r} "
                f"(FIELDS={list(cls.FIELDS)})"
            )

    @classmethod
    def _file_path(cls, field: str) -> Path:
        cls._validate_field(field)
        return cls._assets_dir() / field

    @classmethod
    def on_created(cls) -> None:
        cls._assets_dir().mkdir(parents=True, exist_ok=True)
        for field in cls.FIELDS:
            path = cls._file_path(field)
            if not path.exists():
                path.write_text("", encoding="utf-8")

    @classmethod
    def purge_self(cls) -> int:
        """Clears every field file that currently exists, in place,
        skipping (not creating) any that's missing. Never raises."""
        cleared = 0
        for field in cls.FIELDS:
            path = cls._file_path(field)
            if path.is_file():
                path.write_bytes(b"")
                cleared += 1
        return cleared

    @classmethod
    def write(cls, field: str, content: str) -> None:
        """Writes `content` to the file named `field`, creating it (and
        this node's home/ directory) first if either doesn't exist yet.
        Raises if `field` isn't one of `FIELDS`."""
        path = cls._file_path(field)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @classmethod
    def _sys_prompt(cls) -> str:
        names = ", ".join(f"`{f}`" for f in cls.FIELDS) or "(no FIELDS declared)"
        return (
            f"## `{cls.__name__}` (a `Tuple`) — a node that manages a fixed "
            f"set of named files\n\n"
            f"This node's entire content is one file per name in FIELDS "
            f"({names}), each file named exactly after its field — no "
            f"prefix, no extension — directly under its own home/ "
            f"directory. Never a directory of otherwise-arbitrary "
            f"agent-written content.\n\n"
            f"A transform that populates this node must NOT let "
            f"`fatass.free(...)` write into this node's home/ directory "
            f"directly (e.g. via `writable=` or by just letting the agent "
            f"edit files there). Instead, capture each result with "
            f"`returns=str` and call `NodeClass.write(field, result)` "
            f"yourself — `write()` creates the file if it doesn't exist "
            f"yet, so this is safe to call unconditionally."
        )

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return cls._sys_prompt()
