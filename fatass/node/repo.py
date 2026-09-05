import subprocess

from .node import Node

_SYS_PROMPT = """## `Repo` — a node whose home/ directory is its own git repository

This node's home/ directory is a git repository in its own right (its own
`.git`, independent of fatass's own repo) — `fatass create` already ran
`git init` there once, right after scaffolding. Treat it like any real git
working tree: `git clone`/`git pull`/commits/branches inside it are all
fair game, via `fatass sh` or a transform's own shell calls."""


class Repo(Node):
    """A `Node` whose home/ directory is managed as its own git
    repository -- `on_created()` runs `git init` there once, right after
    scaffolding."""

    @classmethod
    def on_created(cls) -> None:
        assets_dir = cls._assets_dir()
        assets_dir.mkdir(parents=True, exist_ok=True)
        if not (assets_dir / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=assets_dir, check=True)

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        return _SYS_PROMPT
