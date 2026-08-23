from .apply import ApplyCommand
from .archive import ArchiveCommand
from .build import BuildCommand
from .create import CreateCommand
from .free import FreeCommand
from .modify import ModifyCommand
from .move import MoveCommand
from .remove import RemoveCommand
from .retrieve import RetrieveCommand
from .run import RunCommand

ALL_COMMANDS = [
    RunCommand(),
    ApplyCommand(),
    CreateCommand(),
    FreeCommand(),
    ModifyCommand(),
    MoveCommand(),
    RemoveCommand(),
    ArchiveCommand(),
    RetrieveCommand(),
    BuildCommand(),
]

__all__ = ["ALL_COMMANDS"]
