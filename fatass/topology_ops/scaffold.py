import re
import shutil
from pathlib import Path

from .._internal.naming import pascal_case
from .._internal.paths import HOME_ROOT as _HOME_ROOT
from .._internal.paths import TOPOLOGY_ROOT as _TOPOLOGY_ROOT
from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE, free_topology
from ..errors import TopologyValidationError

_NODE_PY = """import fatass


class {class_name}(fatass.{base_class}):
    pass
"""

_NODE_INIT_PY = """from .{file_stem} import {class_name}

__all__ = ["{class_name}"]
"""

_TRANSFORM_STUB = '''def {name}():
    """TODO: add Node-typed parameters for this transform's dependencies."""
'''


def _node_dir(node_path: str) -> Path:
    return _TOPOLOGY_ROOT / node_path.replace(".", "/")


def _assets_dir(node_path: str) -> Path:
    return _HOME_ROOT / node_path.replace(".", "/")


def _is_node_dir(node_dir: Path) -> bool:
    """A node directory has its own `__init__.py` and a same-named
    `<dirname>.py` sitting next to it — no more fixed "node.py" filename to
    check for, so this is structural rather than a single glob pattern."""
    return (node_dir / "__init__.py").is_file() and (node_dir / f"{node_dir.name}.py").is_file()


def _all_node_paths() -> list[str]:
    """Every node path under fatass/topology/ (dirs with their own
    <dirname>.py), found from the filesystem rather than by importing —
    consistent with the rest of this module, and works against a
    monkeypatched _TOPOLOGY_ROOT in tests."""
    paths = []
    for candidate in _TOPOLOGY_ROOT.rglob("*"):
        if candidate.is_dir() and candidate.name != "__pycache__" and _is_node_dir(candidate):
            paths.append(".".join(candidate.relative_to(_TOPOLOGY_ROOT).parts))
    return paths


def _reference_pattern(node_path: str) -> re.Pattern:
    """Matches `fatass.topology.<node_path>` as a whole dotted segment —
    e.g. matches inside "fatass.topology.a.b.c" for node_path "a.b" (a
    nested reference) but not for node_path "a.bc" (a different node)."""
    return re.compile(r"(?<!\w)fatass\.topology\." + re.escape(node_path) + r"(?!\w)")


def create_node(node_path: str, base_class: str = "Node") -> bool:
    """Scaffold a node's topology package (<name>.py + __init__.py) and its
    home/ assets directory. `base_class` names the `fatass.<base_class>`
    class the new node subclasses — "Node" (the default) for an
    ordinary node, or e.g. "NodeList" for a dynamically-sized list node
    (see NodeList in CLAUDE.md). Doesn't call free(). Returns True if it
    created something, False if the node already existed."""
    node_dir = _node_dir(node_path)
    if node_dir.is_dir():
        return False

    parent = node_dir.parent
    if not parent.is_dir():
        raise TopologyValidationError(
            f"parent of {node_path!r} doesn't exist yet ({parent}) — "
            f"create it first"
        )

    file_stem = node_path.rsplit(".", 1)[-1]
    class_name = pascal_case(file_stem)

    node_dir.mkdir()
    (node_dir / f"{file_stem}.py").write_text(
        _NODE_PY.format(class_name=class_name, base_class=base_class), encoding="utf-8"
    )
    (node_dir / "__init__.py").write_text(
        _NODE_INIT_PY.format(file_stem=file_stem, class_name=class_name), encoding="utf-8"
    )

    assets_dir = _HOME_ROOT / node_path.replace(".", "/")
    assets_dir.mkdir(parents=True, exist_ok=True)
    if not any(assets_dir.iterdir()):
        (assets_dir / ".gitkeep").write_text("", encoding="utf-8")

    return True


def create_transform(node_path: str, transform_name: str) -> bool:
    """Scaffold a transform stub directly in a node's own directory.
    Doesn't call free(). Returns True if it created something, False if the
    transform file already existed."""
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    file_stem = node_path.rsplit(".", 1)[-1]
    if transform_name in (file_stem, "__init__"):
        raise TopologyValidationError(
            f"transform name {transform_name!r} collides with {node_path!r}'s "
            f"own file"
        )

    transform_file = node_dir / f"{transform_name}.py"
    if transform_file.exists():
        return False

    transform_file.write_text(_TRANSFORM_STUB.format(name=transform_name), encoding="utf-8")
    return True


def _rename_own_file(node_dir: Path, old_path: str, new_path: str) -> None:
    """After `move_node`/`copy_node` place a node at `node_dir`, its own
    file/class are still named after `old_path`'s last segment — fine if
    that segment didn't change (e.g. moving "a.b" to "c.b"), but if it did
    (e.g. "parent" -> "renamed") the node's own <name>.py/class/__init__.py
    need renaming too. `_rewrite_references` only fixes *external*
    references to this node; this is the node's own identity."""
    old_stem = old_path.rsplit(".", 1)[-1]
    new_stem = new_path.rsplit(".", 1)[-1]
    if old_stem == new_stem:
        return

    old_class = pascal_case(old_stem)
    new_class = pascal_case(new_stem)

    old_file = node_dir / f"{old_stem}.py"
    source = old_file.read_text(encoding="utf-8")
    old_file.unlink()
    (node_dir / f"{new_stem}.py").write_text(
        source.replace(f"class {old_class}(", f"class {new_class}(", 1), encoding="utf-8"
    )

    init_file = node_dir / "__init__.py"
    init_source = init_file.read_text(encoding="utf-8")
    init_source = init_source.replace(
        f"from .{old_stem} import {old_class}", f"from .{new_stem} import {new_class}"
    ).replace(f'__all__ = ["{old_class}"]', f'__all__ = ["{new_class}"]')
    init_file.write_text(init_source, encoding="utf-8")


def move_node(old_path: str, new_path: str) -> int:
    """Move a node (and any nested nodes under it) from `old_path` to
    `new_path`, both under fatass/topology/ and home/, then rewrite
    `fatass.topology.<old_path>` references elsewhere in the topology tree
    to point at `new_path` — other transforms depend on a node by that
    dotted path (see `Node._topology_path`), and a move must keep them
    resolvable. Doesn't call free(). Returns the number of files whose
    references were rewritten."""
    if new_path == old_path:
        raise TopologyValidationError(f"{old_path!r} is already at that path")
    if new_path.startswith(old_path + "."):
        raise TopologyValidationError(
            f"can't move {old_path!r} into its own subtree ({new_path!r})"
        )

    old_node_dir = _node_dir(old_path)
    new_node_dir = _node_dir(new_path)
    old_assets_dir = _assets_dir(old_path)
    new_assets_dir = _assets_dir(new_path)

    if not old_node_dir.is_dir():
        raise TopologyValidationError(f"no node at {old_path!r}")
    if not old_assets_dir.is_dir():
        raise TopologyValidationError(
            f"{old_path!r} has no corresponding home/ directory "
            f"(expected {old_assets_dir}) — topology and home/ have "
            f"already diverged, refusing to move"
        )

    collisions = [d for d in (new_node_dir, new_assets_dir) if d.exists()]
    if collisions:
        raise TopologyValidationError(
            f"{new_path!r} already exists at: "
            f"{', '.join(str(d) for d in collisions)}"
        )

    new_node_parent = new_node_dir.parent
    if not new_node_parent.is_dir():
        raise TopologyValidationError(
            f"parent of {new_path!r} doesn't exist yet ({new_node_parent}) "
            f"— create it first"
        )

    shutil.move(str(old_node_dir), str(new_node_dir))
    _rename_own_file(new_node_dir, old_path, new_path)

    new_assets_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_assets_dir), str(new_assets_dir))

    return _rewrite_references(old_path, new_path)


def copy_node(old_path: str, new_path: str) -> int:
    """Copy a node (and any nodes nested under it) from `old_path` to
    `new_path`, both under fatass/topology/ and home/, leaving the
    original untouched. Only files inside the *copy* are touched
    afterward: any `fatass.topology.<old_path>` reference found there —
    i.e. a dependency between the copied node's own subnodes — is
    rewritten to `new_path`, so it stays relative to the copy rather than
    pointing back at the original. A reference to anything outside the
    copied subtree (an outgoing dependency) doesn't match that pattern and
    is left unchanged, and nothing outside the copy is ever touched, so
    existing dependents of `old_path` keep pointing at the original.
    Doesn't call free(). Returns the number of files whose references were
    rewritten."""
    if new_path == old_path:
        raise TopologyValidationError(f"{old_path!r} is already at that path")
    if new_path.startswith(old_path + "."):
        raise TopologyValidationError(
            f"can't copy {old_path!r} into its own subtree ({new_path!r})"
        )

    old_node_dir = _node_dir(old_path)
    new_node_dir = _node_dir(new_path)
    old_assets_dir = _assets_dir(old_path)
    new_assets_dir = _assets_dir(new_path)

    if not old_node_dir.is_dir():
        raise TopologyValidationError(f"no node at {old_path!r}")
    if not old_assets_dir.is_dir():
        raise TopologyValidationError(
            f"{old_path!r} has no corresponding home/ directory "
            f"(expected {old_assets_dir}) — topology and home/ have "
            f"already diverged, refusing to copy"
        )

    collisions = [d for d in (new_node_dir, new_assets_dir) if d.exists()]
    if collisions:
        raise TopologyValidationError(
            f"{new_path!r} already exists at: "
            f"{', '.join(str(d) for d in collisions)}"
        )

    new_node_parent = new_node_dir.parent
    if not new_node_parent.is_dir():
        raise TopologyValidationError(
            f"parent of {new_path!r} doesn't exist yet ({new_node_parent}) "
            f"— create it first"
        )

    shutil.copytree(str(old_node_dir), str(new_node_dir))
    _rename_own_file(new_node_dir, old_path, new_path)

    new_assets_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(old_assets_dir), str(new_assets_dir))

    return _rewrite_references(old_path, new_path, root=new_node_dir)


def _rewrite_references(old_path: str, new_path: str, root: Path | None = None) -> int:
    """Rewrite every `fatass.topology.<old_path>` reference (import
    statements, and the `<old_path>.transforms.<name>` dotted addressing
    used elsewhere) under `root` (the whole topology tree by default) to
    `new_path`. Matches `old_path` as a whole dotted segment, so moving or
    copying "a.b" also fixes up references to its nested nodes ("a.b.c" ->
    "new.a.b.c"). `copy_node` passes the copy's own directory as `root`,
    so only references between the copy's own subnodes are rewritten —
    everything outside that directory, including the original subtree, is
    left untouched."""
    root = root if root is not None else _TOPOLOGY_ROOT
    pattern = _reference_pattern(old_path)
    replacement = f"fatass.topology.{new_path}"

    updated = 0
    for file in root.rglob("*.py"):
        text = file.read_text(encoding="utf-8")
        new_text = pattern.sub(replacement, text)
        if new_text != text:
            file.write_text(new_text, encoding="utf-8")
            updated += 1
    return updated


def remove_node(node_path: str) -> None:
    """Remove a node and any nodes nested under it, from both
    fatass/topology/ and home/. Refuses if any transform outside the
    removed subtree still references one of the removed nodes as a
    dependency (via `fatass.topology.<removed path>`) — that transform
    would be left unable to resolve the import. Doesn't call free()."""
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")

    removed = {
        p for p in _all_node_paths() if p == node_path or p.startswith(node_path + ".")
    }
    patterns = {p: _reference_pattern(p) for p in removed}

    dependents = []
    for file in _TOPOLOGY_ROOT.rglob("*.py"):
        if node_dir in file.parents:
            continue  # a file inside the subtree being removed
        text = file.read_text(encoding="utf-8")
        for dep_path, pattern in patterns.items():
            if pattern.search(text):
                dependents.append(
                    f"{file.relative_to(_TOPOLOGY_ROOT).as_posix()} (depends on {dep_path})"
                )

    if dependents:
        raise TopologyValidationError(
            f"can't remove {node_path!r}: still depended on by "
            f"{', '.join(sorted(dependents))}"
        )

    shutil.rmtree(node_dir)

    assets_dir = _assets_dir(node_path)
    if assets_dir.is_dir():
        shutil.rmtree(assets_dir)


def remove_transform(node_path: str, transform_name: str) -> None:
    """Remove a single transform file from a node's own directory. Doesn't
    call free(). Nothing else in the topology tree can depend on a
    transform (only on a node's home/ directory), so unlike remove_node
    there's no cross-file check to make here."""
    node_dir = _node_dir(node_path)
    file_stem = node_path.rsplit(".", 1)[-1]
    if transform_name in (file_stem, "__init__"):
        raise TopologyValidationError(
            f"{transform_name!r} is {node_path!r}'s own file, not a transform"
        )
    transform_file = node_dir / f"{transform_name}.py"
    if not transform_file.is_file():
        raise TopologyValidationError(
            f"no transform named {transform_name!r} under {node_path!r}"
        )
    transform_file.unlink()


def refine_node(
    node_path: str,
    prompt: str,
    *,
    system_prompt: str | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> None:
    """Use the Claude CLI to edit a node's own file per `prompt` — either
    right after create_node(), or standalone (`fatass modify`) against an
    already-existing node. Can't go through fatass.free() — that always
    writes into a node's home/ directory, but this is editing the topology
    definition itself, under fatass/topology/."""
    node_dir = _node_dir(node_path)
    file_stem = node_path.rsplit(".", 1)[-1]
    if not (node_dir / f"{file_stem}.py").is_file():
        raise TopologyValidationError(f"no node at {node_path!r}")
    full_prompt = f"Edit {file_stem}.py in the current directory according to: {prompt}"
    free_topology(
        cwd=node_dir,
        prompt=full_prompt,
        system_prompt=system_prompt,
        permission_mode=permission_mode,
        silent=silent,
        model=model,
        tools=tools,
    )


def refine_transform(
    node_path: str,
    transform_name: str,
    prompt: str,
    *,
    system_prompt: str | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> None:
    """Use the Claude CLI to edit a transform file per `prompt` — either
    right after create_transform(), or standalone (`fatass modify`) against
    an already-existing transform (same reasoning as refine_node — this
    writes into fatass/topology/, not home/, so it can't use free())."""
    node_dir = _node_dir(node_path)
    if not (node_dir / f"{transform_name}.py").is_file():
        raise TopologyValidationError(
            f"no transform named {transform_name!r} under {node_path!r}"
        )
    full_prompt = (
        f"Edit {transform_name}.py in the current directory according to: "
        f"{prompt}. It must define a function named {transform_name}. Any "
        f"parameter type-annotated with a Node subclass imported from "
        f"fatass.topology.<dependency node path> declares a dependency on "
        f"that node — follow the convention described in your system "
        f"prompt (you don't have read access to other nodes to check by "
        f"example). A transform with no such parameters is also valid "
        f"(it declares no dependencies)."
    )
    free_topology(
        cwd=node_dir,
        prompt=full_prompt,
        system_prompt=system_prompt,
        permission_mode=permission_mode,
        silent=silent,
        model=model,
        tools=tools,
    )
