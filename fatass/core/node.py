from pathlib import Path

from .._internal.paths import HOME_ROOT

_TOPOLOGY_PREFIX = "fatass.topology."


class Node:
    """Base class for a node's definition.

    Subclassed once per `fatass/topology/.../<name>/<name>.py`. Carries no
    per-instance state — all path resolution is derived from where the
    subclass is defined (`cls.__module__`).
    """

    @classmethod
    def _topology_path(cls) -> str:
        module = cls.__module__
        if not module.startswith(_TOPOLOGY_PREFIX):
            raise ValueError(
                f"{cls!r} is not defined under fatass.topology "
                f"(module is {module!r})"
            )
        path = module[len(_TOPOLOGY_PREFIX):]
        # A Node subclass is defined inside its own <name>.py, so
        # cls.__module__ is always "...<name>.<name>" — one trailing segment
        # (the node's own file, always named after its own directory) more
        # than the node's actual topology path. Strip it unconditionally.
        return path.rsplit(".", 1)[0]

    @classmethod
    def _assets_dir(cls) -> Path:
        relative = cls._topology_path().replace(".", "/")
        return HOME_ROOT / relative

    @classmethod
    def create_sys_prompt(cls) -> str | None:
        """Extra `--append-system-prompt` guidance for `fatass create`
        when scaffolding a node file that subclasses this class — appended
        after the static conventions/command prompts. None by default;
        override in a subclass (see NodeList) to teach the agent
        conventions specific to that kind of node."""
        return None

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        """Same as create_sys_prompt(), but for `fatass modify` against an
        already-existing node of this class."""
        return None
