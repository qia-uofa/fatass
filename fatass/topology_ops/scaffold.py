import ast
import re
import shutil
from pathlib import Path

from .._internal.naming import pascal_case
from .._internal.paths import HOME_ROOT as _HOME_ROOT
from .._internal.paths import LOG_PATH as _LOG_PATH
from .._internal.paths import SHELL_HISTORY_PATH as _SHELL_HISTORY_PATH
from .._internal.paths import TOPOLOGY_ROOT as _TOPOLOGY_ROOT
from .._internal.prompts import load_topology_edit_system_prompt
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
    ordinary node, or e.g. "Chain" for a dynamically-sized list node
    (see Chain in CLAUDE.md). Doesn't call free(). Returns True if it
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


def _line_start(source: str, lineno: int) -> int:
    """Byte offset of the start of 1-indexed `lineno` in `source`."""
    pos = 0
    for _ in range(lineno - 1):
        pos = source.index("\n", pos) + 1
    return pos


def _rewrite_self_imports(node_dir: Path, old_stem: str, new_stem: str, new_class: str) -> None:
    """A transform file sitting in the same directory as the node's own
    file can import that node's own class via a *relative* self-import
    (e.g. `from .search_result import SearchResult`, used to find its
    own node's `_assets_dir()` without hardcoding a path) — unlike
    `_rewrite_references`'s *absolute* `fatass.topology.<path>` pattern,
    a same-directory relative import never spells out the full topology
    path, so it isn't caught there. `_rename_own_file` already renamed
    the file itself and fixed `__init__.py`'s own import; this fixes
    every other `.py` file in the directory (transforms) that relied on
    the old module name — aliasing the new class back to whatever local
    name the file already used for it (`from .{new_stem} import
    {new_class} as <that name>`), so nothing else in the file (in
    particular a transform's own prompt text) needs to change."""
    for file in node_dir.glob("*.py"):
        if file.name in ("__init__.py", f"{new_stem}.py"):
            continue
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        target = next(
            (
                n
                for n in tree.body
                if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module == old_stem
            ),
            None,
        )
        if target is None:
            continue

        alias = target.names[0].asname or target.names[0].name
        abs_start = _line_start(source, target.lineno) + target.col_offset
        abs_end = _line_start(source, target.end_lineno) + target.end_col_offset
        new_source = (
            source[:abs_start]
            + f"from .{new_stem} import {new_class} as {alias}"
            + source[abs_end:]
        )
        file.write_text(new_source, encoding="utf-8")


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

    _rewrite_self_imports(node_dir, old_stem, new_stem, new_class)


def _files_still_mention(node_dir: Path, *needles: str) -> bool:
    """True if any `.py` file directly in `node_dir` (not recursive —
    same scope `_rename_own_file`/`_rewrite_self_imports` operate in)
    still contains any of `needles` as a whole word/identifier — used to
    check, *after* the mechanical rewrites have already run, whether
    anything's actually left for `_review_renamed_stem` to ask an agent
    about. A whole-word match (not a bare substring) so e.g. needle "old"
    doesn't false-positive on "older_result"."""
    patterns = [re.compile(r"(?<!\w)" + re.escape(n) + r"(?!\w)") for n in needles if n]
    if not patterns:
        return False
    for file in node_dir.glob("*.py"):
        text = file.read_text(encoding="utf-8")
        if any(p.search(text) for p in patterns):
            return True
    return False


def _review_renamed_stem(node_dir: Path, old_path: str, new_path: str) -> None:
    """After `move_node` renames a node's own leaf segment (e.g. "parent"
    -> "renamed" in "a.parent" -> "a.renamed"), `_rename_own_file`/
    `_rewrite_self_imports`/`_rewrite_external_class_imports` already
    fixed everything a mechanical text substitution can find: the class
    definition, `__init__.py`'s import, every same-directory transform's
    self-import, and every external absolute import of the old class
    name. None of that can catch things that only reading the code and
    prose actually reveals — a local variable named after the old stem, a
    mention of the old name inside a `fatass.free(...)` prompt string, a
    comment — so this opens a real, interactive (`silent=False`)
    `fatass.free()` conversation scoped to the node's own directory,
    asking the agent to review and fix exactly that.

    A no-op (returns immediately, no agent call) if the leaf segment
    didn't actually change (the common case, e.g. "a.b" -> "c.b"), *or*
    if it did change but `_files_still_mention` finds no remaining trace
    of the old name (stem or class name) in any of this directory's
    files — the mechanical rewrites already covered every reference that
    existed, so there's nothing left to review."""
    old_stem = old_path.rsplit(".", 1)[-1]
    new_stem = new_path.rsplit(".", 1)[-1]
    if old_stem == new_stem:
        return
    if not _files_still_mention(node_dir, old_stem, pascal_case(old_stem)):
        return

    prompt = (
        f"This node was just renamed from {old_stem!r} to {new_stem!r} "
        f"(full path: {old_path!r} -> {new_path!r}) by `fatass move`. The "
        f"mechanical rename already updated the node's own class "
        f"definition, `__init__.py`'s import, and every same-directory "
        f"transform's self-import of the class — that part is done, don't "
        f"redo it. What a plain text substitution can't catch is anything "
        f"that only reading the code and prose reveals: a local variable "
        f"named after the old stem ({old_stem!r}), a mention of "
        f"{old_stem!r} inside a `fatass.free(...)` prompt string, a "
        f"comment, a docstring. Review every .py file in the current "
        f"directory (the node's own class file and each transform) for "
        f"exactly that, and fix whatever you find so it consistently "
        f"reflects the new name {new_stem!r} — but change nothing "
        f"unrelated to the rename."
    )
    free_topology(
        cwd=node_dir,
        prompt=prompt,
        silent=False,
        system_prompt=load_topology_edit_system_prompt("move"),
    )


def _rewrite_external_class_imports(
    root: Path, new_path: str, old_class: str, new_class: str
) -> None:
    """`_rewrite_references` retargets `fatass.topology.<old_path>` ->
    `fatass.topology.<new_path>` in every dependent file, but if the move/
    copy also renamed the node's own class (see `_rename_own_file` — the
    leaf segment changed, e.g. "uni_candidates" -> "unis"), an absolute
    import that named the old class explicitly (`from
    fatass.topology.<new_path> import <old_class>[ as <alias>]`) now asks
    the new module for a name it no longer exports. Fix those up too,
    aliasing the new class back to whatever local name the importing file
    already used, so nothing else in that file (in particular a
    transform's own prompt text or its parameter names) needs to change —
    mirroring `_rewrite_self_imports`'s approach for same-directory
    transforms, but for absolute imports anywhere under `root`."""
    module = f"fatass.topology.{new_path}"
    for file in root.rglob("*.py"):
        source = file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        match = next(
            (
                (imp, alias)
                for imp in ast.walk(tree)
                if isinstance(imp, ast.ImportFrom) and imp.module == module
                for alias in imp.names
                if alias.name == old_class
            ),
            None,
        )
        if match is None:
            continue

        imp, alias = match
        local = alias.asname or alias.name
        abs_start = _line_start(source, imp.lineno) + imp.col_offset
        abs_end = _line_start(source, imp.end_lineno) + imp.end_col_offset
        new_source = (
            source[:abs_start]
            + f"from {module} import {new_class} as {local}"
            + source[abs_end:]
        )
        file.write_text(new_source, encoding="utf-8")


def _rewrite_external_references(old_path: str, new_path: str, root: Path | None = None) -> int:
    """Combines `_rewrite_references` (module path) with
    `_rewrite_external_class_imports` (imported class name, only if the
    leaf segment/class actually changed) — the two fixes a move/copy of a
    renamed node needs everywhere outside the node's own directory."""
    updated = _rewrite_references(old_path, new_path, root=root)
    old_stem = old_path.rsplit(".", 1)[-1]
    new_stem = new_path.rsplit(".", 1)[-1]
    if old_stem != new_stem:
        _rewrite_external_class_imports(
            root if root is not None else _TOPOLOGY_ROOT,
            new_path,
            pascal_case(old_stem),
            pascal_case(new_stem),
        )
    return updated


def _notify_parent_of_child_move(old_path: str, new_path: str) -> None:
    """After a node's own topology/home/ directories are relocated,
    give its *parent's* class a chance to react — e.g. a `Chain`
    mirrors its schema children's names into every existing `.next`
    level (see `Chain.on_child_moved`), content `move_node` itself has
    no notion of. Only fires for an in-place rename (same parent, leaf
    segment changed) — moving a node to a different parent entirely, or
    moving it without renaming it, needs no such reaction. Best-effort:
    a parent that fails to import (e.g. it's mid-edit) just means no
    hook runs, not a failed move — the move itself already succeeded."""
    if "." not in old_path or "." not in new_path:
        return
    old_parent, old_stem = old_path.rsplit(".", 1)
    new_parent, new_stem = new_path.rsplit(".", 1)
    if old_parent != new_parent or old_stem == new_stem:
        return

    from ..core.transform import _import_node  # local import: avoid a cycle

    try:
        parent_cls = _import_node(old_parent)
    except Exception:
        return
    parent_cls.on_child_moved(old_stem, new_stem)


def move_node(old_path: str, new_path: str) -> int:
    """Move a node (and any nested nodes under it) from `old_path` to
    `new_path`, both under fatass/topology/ and home/, then rewrite
    `fatass.topology.<old_path>` references elsewhere in the topology tree
    to point at `new_path` — other transforms depend on a node by that
    dotted path (see `Node._topology_path`), and a move must keep them
    resolvable. If the node's own leaf segment changed (not just its
    parent — e.g. "a.old" -> "a.new", not "a.old" -> "b.old"), this also
    opens a real, interactive `free()` conversation (see
    `_review_renamed_stem`) once every mechanical rewrite is done, asking
    the agent to catch anything a text substitution can't — a variable
    name, a prompt string, a comment still referencing the old name.
    Returns the number of files whose references were rewritten."""
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

    _notify_parent_of_child_move(old_path, new_path)

    updated = _rewrite_external_references(old_path, new_path)
    _review_renamed_stem(new_node_dir, old_path, new_path)
    return updated


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

    return _rewrite_external_references(old_path, new_path, root=new_node_dir)


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

    # Local import: topology_ops.bind imports _node_dir from this module,
    # so importing it back at module level here would be a cycle.
    from .bind import bound_dep_paths

    dep_paths = bound_dep_paths(node_path, transform_name)
    add_dirs = [_node_dir(dep_path) for dep_path in dep_paths]

    full_prompt = (
        f"Edit {transform_name}.py in the current directory according to: "
        f"{prompt}. It must define a function named {transform_name}. Any "
        f"parameter type-annotated with a Node subclass imported from "
        f"fatass.topology.<dependency node path> declares a dependency on "
        f"that node — follow the convention described in your system "
        f"prompt (you don't have read access to other nodes to check by "
        f"example). A transform with no such parameters is also valid "
        f"(it declares no dependencies). You've been granted read access "
        f"to this transform's already-declared dependency nodes' own "
        f"topology directories (not their home/ assets) — nothing else."
    )
    free_topology(
        cwd=node_dir,
        prompt=full_prompt,
        add_dirs=add_dirs,
        system_prompt=system_prompt,
        permission_mode=permission_mode,
        silent=silent,
        model=model,
        tools=tools,
    )


_LOG_EXCERPT_MAX_LINES = 400
_LOG_EXCERPT_MAX_CHARS = 20_000

_DEBUG_PROMPT_MARKER = "Recent history for this transform from ./log"
"""Unique text `debug_transform` puts in every prompt it builds (see
`log_section` below) — `_log_excerpt` skips any ./log line containing it,
since that line *is* a previous `debug` call's own logged prompt, not
genuine history about the transform. Without this, each debug call's
prompt embeds ./log, which then logs that same prompt right back into
./log — so the next debug call would re-embed the previous one's already-
embedded copy, compounding every single call (observed in practice:
27k -> 139k -> 329k -> 810k characters over four calls) until the
resulting command line is too long for the OS to launch at all."""


def _log_excerpt(node_path: str, transform_name: str) -> str | None:
    """The tail of ./log's lines relevant to this transform — both its own
    command-dispatch lines (`<current> run <transform>@<node> -> exit ...`)
    and any free() call it made (cwd=<its home dir>, prompt=..., stdout=...,
    stderr=...) — read directly here and spliced into the debug prompt,
    rather than granting the agent the whole repo root as a directory just
    to read one file. Returns None if the log doesn't exist or nothing in
    it matches this transform.

    Excludes any line containing `_DEBUG_PROMPT_MARKER` (a previous debug
    call's own logged prompt — see there) to avoid runaway self-embedding,
    and hard-caps the final excerpt's total length at
    `_LOG_EXCERPT_MAX_CHARS` (keeping the tail) as a second, independent
    backstop against any other way a single ./log line could end up huge."""
    if not _LOG_PATH.is_file():
        return None
    home_dir = str(_assets_dir(node_path))
    label = f"{node_path}.transforms.{transform_name}"
    matches = [
        line
        for line in _LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        if (label in line or home_dir in line) and _DEBUG_PROMPT_MARKER not in line
    ]
    if not matches:
        return None
    excerpt = "\n".join(matches[-_LOG_EXCERPT_MAX_LINES:])
    if len(excerpt) > _LOG_EXCERPT_MAX_CHARS:
        excerpt = excerpt[-_LOG_EXCERPT_MAX_CHARS:]
    return excerpt


_SHELL_HISTORY_MAX_ENTRIES = 100


def _shell_history_excerpt() -> str | None:
    """The tail of `fatass shell`'s own persisted `>>> ` line history
    (.fatass/shell_history, prompt_toolkit FileHistory format — see
    commands/shell.py) — unlike _log_excerpt, not scoped to this
    transform at all (a raw command history has no notion of which
    fatass node a line related to), so this is unfiltered recent context:
    whatever was typed at the `>>> ` prompt just before/around the
    failure, across every past `fatass shell` session, not just the OS
    terminal's own (bash/PowerShell) history — that history includes
    plenty that has nothing to do with fatass, where this is exactly the
    fatass commands that were actually run. Returns None if the file
    doesn't exist or has no entries yet."""
    if not _SHELL_HISTORY_PATH.is_file():
        return None
    # Local import: prompt_toolkit is otherwise only a `shell` dependency;
    # importing it at module level here would pull it into every command.
    from prompt_toolkit.history import FileHistory

    # load_history_strings() yields most-recent-first; take the newest
    # _SHELL_HISTORY_MAX_ENTRIES, then reverse back to chronological order.
    entries = []
    for entry in FileHistory(str(_SHELL_HISTORY_PATH)).load_history_strings():
        entries.append(entry)
        if len(entries) >= _SHELL_HISTORY_MAX_ENTRIES:
            break
    if not entries:
        return None
    return "\n".join(reversed(entries))


def debug_transform(
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
    """Use the Claude CLI to debug a failing transform — same underlying
    edit as refine_transform (writes into fatass/topology/, so it goes
    through free_topology(), not free()), but framed around root-causing a
    failure instead of an open-ended instruction: grants read access to
    the transform's already-declared dependency nodes (same as
    refine_transform) plus its own home/ output directory (to inspect
    whatever it already wrote, including any partial/broken output) —
    input and output nodes only, nothing else. Also inlines two sources
    of history directly into the prompt: the relevant tail of ./log (this
    transform's own past command-dispatch and free() call history — cwd,
    args, exit code, stdout/stderr) and the tail of the real shell's
    command history (see _shell_history_excerpt — unfiltered, not scoped
    to this transform)."""
    node_dir = _node_dir(node_path)
    if not (node_dir / f"{transform_name}.py").is_file():
        raise TopologyValidationError(
            f"no transform named {transform_name!r} under {node_path!r}"
        )

    # Local import: topology_ops.bind imports _node_dir from this module,
    # so importing it back at module level here would be a cycle.
    from .bind import bound_dep_paths

    dep_paths = bound_dep_paths(node_path, transform_name)
    home_dir = _assets_dir(node_path)
    home_dir.mkdir(parents=True, exist_ok=True)
    add_dirs = [_node_dir(dep_path) for dep_path in dep_paths] + [home_dir]

    log_excerpt = _log_excerpt(node_path, transform_name)
    log_section = (
        f"\n\n{_DEBUG_PROMPT_MARKER} (the repo root's fatass invocation "
        f"log — past command dispatches and free() call arguments/exit "
        f"codes/stdout/stderr):\n\n{log_excerpt}"
        if log_excerpt
        else "\n\nNo matching history was found in ./log for this transform."
    )

    shell_history = _shell_history_excerpt()
    shell_section = (
        f"\n\nRecent shell command history (unfiltered — not specific to "
        f"this transform, just whatever was run around this time):"
        f"\n\n{shell_history}"
        if shell_history
        else "\n\nNo shell command history was found to read."
    )

    full_prompt = (
        f"Debug {transform_name}.py in the current directory. "
        f"{prompt}{log_section}{shell_section}\n\nYou've been granted read "
        f"access to this transform's own home/ output directory (where its "
        f"fatass.free(...) calls actually write, at {home_dir}) and its "
        f"already-declared dependency nodes' topology directories — "
        f"inspect whatever it already wrote (including any partial or "
        f"broken output) alongside the history above to find the root "
        f"cause, then fix {transform_name}.py."
    )
    free_topology(
        cwd=node_dir,
        prompt=full_prompt,
        add_dirs=add_dirs,
        system_prompt=system_prompt,
        permission_mode=permission_mode,
        silent=silent,
        model=model,
        tools=tools,
    )
