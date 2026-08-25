import datetime
import re
import shutil
from pathlib import Path

from .._internal.paths import ARCHIVE_ROOT, HOME_ROOT, TOPOLOGY_ROOT
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
    "empty" for archive/retrieve, without also inspecting home/."""
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


def _is_node_dir(node_dir: Path) -> bool:
    return (node_dir / "__init__.py").is_file() and (node_dir / f"{node_dir.name}.py").is_file()


def _all_node_paths() -> list[str]:
    """Every node path under fatass/topology/ (dirs with their own
    <dirname>.py) — a local copy of scaffold._all_node_paths that reads
    through *this* module's own TOPOLOGY_ROOT binding, since tests
    monkeypatch `archive.TOPOLOGY_ROOT` specifically (not scaffold's)."""
    paths = []
    for candidate in TOPOLOGY_ROOT.rglob("*"):
        if candidate.is_dir() and candidate.name != "__pycache__" and _is_node_dir(candidate):
            paths.append(".".join(candidate.relative_to(TOPOLOGY_ROOT).parts))
    return paths


def _reference_pattern(node_path: str) -> re.Pattern:
    """Matches `fatass.topology.<node_path>` as a whole dotted segment —
    same convention as scaffold._reference_pattern."""
    return re.compile(r"(?<!\w)fatass\.topology\." + re.escape(node_path) + r"(?!\w)")


def _dependents_outside(node_path: str, node_dir: Path) -> list[str]:
    """Every file outside `node_dir` that still references `node_path` (or
    one of its nested nodes) via `fatass.topology.<...>` — the same check
    `remove_node` makes, reused here since archiving a still-depended-on
    node would leave those references unresolvable too."""
    removed = {
        p for p in _all_node_paths() if p == node_path or p.startswith(node_path + ".")
    }
    patterns = {p: _reference_pattern(p) for p in removed}

    dependents = []
    for file in TOPOLOGY_ROOT.rglob("*.py"):
        if node_dir in file.parents:
            continue
        text = file.read_text(encoding="utf-8")
        for dep_path, pattern in patterns.items():
            if pattern.search(text):
                dependents.append(
                    f"{file.relative_to(TOPOLOGY_ROOT).as_posix()} (depends on {dep_path})"
                )
    return dependents


def _archive_node(dest: Path, node_path: str) -> None:
    """Move just `node_path`'s own subtree (topology dir + home dir) into
    `dest`, mirrored at the same relative path it had, leaving the rest of
    the live topology untouched. Unlike the whole-topology case, nothing
    fresh is recreated at the archived node's old location — it's just
    gone, same as `remove_node`; run `fatass create` again there for a new
    node."""
    rel = node_path.replace(".", "/")
    node_dir = TOPOLOGY_ROOT / rel
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    dependents = _dependents_outside(node_path, node_dir)
    if dependents:
        raise TopologyValidationError(
            f"can't archive {node_path!r}: still depended on by "
            f"{', '.join(sorted(dependents))}"
        )

    dest_topology = dest / "topology" / rel
    dest_topology.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(node_dir), str(dest_topology))

    home_dir = HOME_ROOT / rel
    if home_dir.is_dir():
        dest_home = dest / "home" / rel
        dest_home.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(home_dir), str(dest_home))


def archive_topology(name: str | None = None, node_path: str | None = None) -> str:
    """Move the current fatass/topology/ and home/ trees into
    ./archive/<name>-<timestamp>/ (or just <timestamp>/ if `name` is
    omitted), then recreate both fresh and empty. Returns the archive
    directory's name.

    With `node_path` given, only that node's own subtree is archived
    instead of the whole topology: moved out to the same relative path
    under the snapshot, refusing (like `remove_node`) if anything outside
    the subtree still depends on it. The rest of the live topology is left
    exactly as it was — no fresh-and-empty reset, since nothing else was
    touched."""
    dir_name = f"{name}-{_timestamp()}" if name else _timestamp()
    dest = ARCHIVE_ROOT / dir_name
    if dest.exists():
        raise TopologyValidationError(f"archive {dir_name!r} already exists")

    if node_path is not None:
        dest.mkdir(parents=True)
        _archive_node(dest, node_path)
        return dir_name

    dest.mkdir(parents=True)

    shutil.move(str(TOPOLOGY_ROOT), str(dest / "topology"))
    TOPOLOGY_ROOT.mkdir()
    (TOPOLOGY_ROOT / "__init__.py").write_text(_TOPOLOGY_INIT_PY, encoding="utf-8")

    if HOME_ROOT.is_dir():
        shutil.move(str(HOME_ROOT), str(dest / "home"))
    HOME_ROOT.mkdir(parents=True, exist_ok=True)

    return dir_name


def _restore(src: Path) -> None:
    """Copy an archived snapshot's topology/ and home/ back into place,
    over the current (already-fresh-and-empty) ones — a copy, not a move,
    so the archive stays available for a later retrieve."""
    shutil.rmtree(TOPOLOGY_ROOT)
    shutil.copytree(src / "topology", TOPOLOGY_ROOT)

    if HOME_ROOT.is_dir():
        shutil.rmtree(HOME_ROOT)
    if (src / "home").is_dir():
        shutil.copytree(src / "home", HOME_ROOT)
    else:
        HOME_ROOT.mkdir(parents=True, exist_ok=True)


def retrieve_topology(name: str | None = None) -> str:
    """Restore an archived snapshot into fatass/topology/ and home/.
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


def retrieve_node(name: str, node_path: str) -> str:
    """Restore one node's subtree from the archive labeled `name` back to
    its original relative path under fatass/topology/ and home/. Requires
    `name` — unlike the whole-topology toggle, there's no single "latest"
    notion for an individual node across possibly-unrelated archives, so
    it must be named explicitly. Refuses if a node already exists at that
    path (archive or remove it first) or if that archive holds no such
    node. Returns the name of the archive directory restored from."""
    src = _latest_named(name)
    if src is None:
        raise TopologyValidationError(f"no archive named {name!r}")

    rel = node_path.replace(".", "/")
    src_topology = src / "topology" / rel
    if not src_topology.is_dir():
        raise TopologyValidationError(f"archive {name!r} has no node at {node_path!r}")

    node_dir = TOPOLOGY_ROOT / rel
    if node_dir.exists():
        raise TopologyValidationError(
            f"{node_path!r} already exists — archive or remove it first"
        )

    node_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_topology, node_dir)

    src_home = src / "home" / rel
    if src_home.is_dir():
        home_dir = HOME_ROOT / rel
        home_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_home, home_dir)

    return src.name
