from .apply import ApplyCommand
from .archive import ArchiveCommand
from .build import BuildCommand
from .cd import CdCommand
from .copy import CopyCommand
from .create import CreateCommand
from .free import FreeCommand
from .graph import GraphCommand
from .modify import ModifyCommand
from .move import MoveCommand
from .purge import PurgeCommand
from .pwd import PwdCommand
from .remove import RemoveCommand
from .retrieve import RetrieveCommand
from .run import RunCommand
from .sh import ShCommand
from .shell import ShellCommand

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
    ShellCommand(),
]

__all__ = ["ALL_COMMANDS"]
