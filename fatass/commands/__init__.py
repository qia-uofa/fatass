from .apply import ApplyCommand
from .archive import ArchiveCommand
from .bind import BindCommand
from .build import BuildCommand
from .cd import CdCommand
from .chat_new import ChatNewCommand
from .copy import CopyCommand
from .create import CreateCommand
from .debug import DebugCommand
from .dict_keys import DictKeysCommand
from .dict_pop import DictPopCommand
from .dict_set import DictSetCommand
from .dir_mirror import DirMirrorCommand
from .dir_path import DirPathCommand
from .dir_set_path import DirSetPathCommand
from .free import FreeCommand
from .graph import GraphCommand
from .gui import GuiCommand
from .init import InitCommand
from .insert import InsertCommand
from .length import LenCommand
from .ls import LsCommand
from .modify import ModifyCommand
from .move import MoveCommand
from .pop import PopCommand
from .purge import PurgeCommand
from .push import PushCommand
from .pwd import PwdCommand
from .remove import RemoveCommand
from .retrieve import RetrieveCommand
from .run import RunCommand
from .sh import ShCommand
from .shell import ShellCommand
from .touch import TouchCommand
from .unbind import UnbindCommand
from .vim import VimCommand

ALL_COMMANDS = [
    RunCommand(),
    ApplyCommand(),
    CreateCommand(),
    FreeCommand(),
    DebugCommand(),
    ModifyCommand(),
    MoveCommand(),
    CopyCommand(),
    RemoveCommand(),
    PurgeCommand(),
    ArchiveCommand(),
    RetrieveCommand(),
    TouchCommand(),
    BuildCommand(),
    InitCommand(),
    ShCommand(),
    CdCommand(),
    PwdCommand(),
    GraphCommand(),
    GuiCommand(),
    LsCommand(),
    BindCommand(),
    UnbindCommand(),
    LenCommand(),
    InsertCommand(),
    PushCommand(),
    PopCommand(),
    DictKeysCommand(),
    DictSetCommand(),
    DictPopCommand(),
    DirPathCommand(),
    DirSetPathCommand(),
    DirMirrorCommand(),
    ChatNewCommand(),
    ShellCommand(),
    VimCommand(),
]

TOP_LEVEL_NAMES = {c.name for c in ALL_COMMANDS if c.group is None} | {
    c.group for c in ALL_COMMANDS if c.group is not None
}
"""Every token that can appear as `argv[0]` on its own — an ungrouped
command's own `.name`, or (once, however many commands share it) a
group's name (e.g. "chain") for a command nested under it. A grouped
command's own `.name` (e.g. "len") is deliberately excluded: it's only
ever valid as the *second* token (`fatass chain len`), never the first."""

GROUP_SUBCOMMAND_NAMES: dict[str, list[str]] = {}
for _command in ALL_COMMANDS:
    if _command.group is not None:
        GROUP_SUBCOMMAND_NAMES.setdefault(_command.group, []).append(_command.name)
del _command
"""Maps each group name (e.g. "chain") to the list of its own nested
commands' names (e.g. ["len", "insert", "push", "pop"]) — for `cli.py`'s
`@`-shorthand check and `shell.py`'s tab-completion, so neither has to
re-derive this from `ALL_COMMANDS` itself."""

__all__ = ["ALL_COMMANDS", "TOP_LEVEL_NAMES", "GROUP_SUBCOMMAND_NAMES"]
