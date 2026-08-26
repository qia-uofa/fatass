from .apply import ApplyCommand
from .archive import ArchiveCommand
from .bind import BindCommand
from .build import BuildCommand
from .cd import CdCommand
from .copy import CopyCommand
from .create import CreateCommand
from .free import FreeCommand
from .graph import GraphCommand
from .ls import LsCommand
from .modify import ModifyCommand
from .move import MoveCommand
from .purge import PurgeCommand
from .pwd import PwdCommand
from .remove import RemoveCommand
from .retrieve import RetrieveCommand
from .run import RunCommand
from .sh import ShCommand
from .shell import ShellCommand
from .unbind import UnbindCommand
from .vim import VimCommand

ALL_COMMANDS = [
    RunCommand(),
    ApplyCommand(),
    CreateCommand(),
    FreeCommand(),
    ModifyCommand(),
    MoveCommand(),
    CopyCommand(),
    RemoveCommand(),
    PurgeCommand(),
    ArchiveCommand(),
    RetrieveCommand(),
    BuildCommand(),
    ShCommand(),
    CdCommand(),
    PwdCommand(),
    GraphCommand(),
    LsCommand(),
    BindCommand(),
    UnbindCommand(),
    ShellCommand(),
    VimCommand(),
]

__all__ = ["ALL_COMMANDS"]
