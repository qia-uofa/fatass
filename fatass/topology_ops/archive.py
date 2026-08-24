import datetime
import re
import shutil
from pathlib import Path

from .._internal.paths import ARCHIVE_ROOT, NODES_ROOT, TOPOLOGY_ROOT
from ..errors import TopologyValidationError

# Microsecond precision: `retrieve_topology()` can call `archive_topology()`
# internally, so two archives can legitimately be created within the same
# wall-clock second — second-only precision would collide.
_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S%f"
_TIMESTAMP_RE = re.compile(r"\d{8}-\d{12}")

_TOPOLOGY_INIT_PY = """from .._internal.import_tree import import_all

import_all(__name__)
"""


def _timestamp() -> str:
    return datetime.datetime.now().strftime(_TIMESTAMP_FORMAT)


def _has_nodes() -> bool:
    """True if fatass/topology/ currently defines at least one node.
    Topology is the source of truth (see
    blueprint/design/topology-validation.md), so this alone decides
    "empty" for archive/retrieve, without also inspecting nodes/."""
    return any(p.is_dir() and p.name != "__pycache__" for p in TOPOLOGY_ROOT.iterdir())


def _archive_dirs() -> list[Path]:
    if not ARCHIVE_ROOT.is_dir():
        return []
    return [p for p in ARCHIVE_ROOT.iterdir() if p.is_dir()]


def _latest_unnamed() -> Path | None:
    """The most recent archive created by `archive_topology(name=None)` — a
    directory named exactly a timestamp, no label prefix."""
    candidates = [p for p in _archive_dirs() if _TIMESTAMP_RE.fullmatch(p.name)]
    return max(candidates, key=lambda p: p.name, default=None)


def _latest_named(name: str) -> Path | None:
    """The most recent archive created by `archive_topology(name=name)`."""
    prefix = f"{name}-"
    candidates = [
        p
        for p in _archive_dirs()
        if p.name.startswith(prefix) and _TIMESTAMP_RE.fullmatch(p.name[len(prefix) :])
    ]
    return max(candidates, key=lambda p: p.name, default=None)


def archive_topology(name: str | None = None) -> str:
    """Move the current fatass/topology/ and nodes/ trees into
    ./archive/<name>-<timestamp>/ (or just <timestamp>/ if `name` is
    omitted), then recreate both fresh and empty. Returns the archive
    directory's name."""
    dir_name = f"{name}-{_timestamp()}" if name else _timestamp()
    dest = ARCHIVE_ROOT / dir_name
    if dest.exists():
        raise TopologyValidationError(f"archive {dir_name!r} already exists")
    dest.mkdir(parents=True)

    shutil.move(str(TOPOLOGY_ROOT), str(dest / "topology"))
    TOPOLOGY_ROOT.mkdir()
    (TOPOLOGY_ROOT / "__init__.py").write_text(_TOPOLOGY_INIT_PY)

    if NODES_ROOT.is_dir():
        shutil.move(str(NODES_ROOT), str(dest / "nodes"))
    NODES_ROOT.mkdir(parents=True, exist_ok=True)

    return dir_name


def _restore(src: Path) -> None:
    """Copy an archived snapshot's topology/ and nodes/ back into place,
    over the current (already-fresh-and-empty) ones — a copy, not a move,
    so the archive stays available for a later retrieve."""
    shutil.rmtree(TOPOLOGY_ROOT)
    shutil.copytree(src / "topology", TOPOLOGY_ROOT)

    if NODES_ROOT.is_dir():
        shutil.rmtree(NODES_ROOT)
    if (src / "nodes").is_dir():
        shutil.copytree(src / "nodes", NODES_ROOT)
    else:
        NODES_ROOT.mkdir(parents=True, exist_ok=True)


def retrieve_topology(name: str | None = None) -> str:
    """Restore an archived snapshot into fatass/topology/ and nodes/.
    Returns the name of the archive directory that was restored.

    With `name`: if the current topology isn't empty, it's archived first
    (unnamed) so it isn't lost, then the latest archive labeled `name` is
    copied in.

    Without `name`: acts as a toggle. If the current topology isn't empty,
    the latest *unnamed* archive (as of before this call) is what gets
    restored, and the current state is itself pushed onto the unnamed
    archive stack first — so calling it again swaps back. If the current
    topology is already empty, it just restores the latest unnamed archive
    (nothing to save first).
    """
    if name is not None:
        if _has_nodes():
            archive_topology()
        src = _latest_named(name)
        if src is None:
            raise TopologyValidationError(f"no archive named {name!r}")
        _restore(src)
        return src.name

    if _has_nodes():
        src = _latest_unnamed()
        if src is None:
            raise TopologyValidationError("no previous archive to retrieve")
        archive_topology()
        _restore(src)
        return src.name

    src = _latest_unnamed()
    if src is None:
        raise TopologyValidationError("no archive to retrieve")
    _restore(src)
    return src.name
