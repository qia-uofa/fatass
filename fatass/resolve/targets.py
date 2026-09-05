import re
from pathlib import Path

from ..node.array import Array
from ..node.single import Single
from ..core.transform import _import_node, _resolve_owning_node, _split_index, resolve_indexed_assets_dir
from ..errors import TopologyValidationError
from ..topology_ops import scaffold
from ..topology_ops.scaffold import _assets_dir, _node_dir
from .cwd import ROOT, expand

_HOME_ROOT_MARKERS = (".", "./")
"""A non-empty `rel` inside "(...)" that still means "the home dir
itself" (an explicit escape hatch — unlike a bare "()", this never
triggers the Single/Array empty-call sugar below)."""

_CALL_PATTERN = re.compile(r"^(?P<node>.+?)\((?P<rel>[^()]*)\)(?:\[(?P<idx>[^\[\]]*)\])?$")
""""node.path(rel/path)" / "node.path()" / "node.path()[i,j,...]" — see
`resolve()`'s docstring. `node` is matched non-greedily up to the first
"(", so a Chain-indexed node path (e.g. "members[2]") is captured whole,
brackets and all — `_split_index` sorts that out afterward."""


def _parse_array_index(raw: str, target: str) -> tuple[int, ...]:
    try:
        return tuple(int(part.strip()) for part in raw.split(","))
    except ValueError:
        raise TopologyValidationError(
            f"invalid index {raw!r} in {target!r} — expected e.g. '[0,1,1]'"
        ) from None


def _assets_base(node_path: str) -> Path:
    """home/ directory for `node_path` — the true root sentinel, a plain
    node, or one indexed into a Chain (`_split_index`/
    `resolve_indexed_assets_dir`, see `fatass.core.transform`). Shared by
    the "(...)" content form and the empty-"()" non-sugar case."""
    if node_path == ROOT:
        return scaffold._HOME_ROOT
    _list_path, index, _suffix = _split_index(node_path)
    if index is None:
        if not _node_dir(node_path).is_dir():
            raise TopologyValidationError(f"no node at {node_path!r}")
        return _assets_dir(node_path)
    return resolve_indexed_assets_dir(node_path)


def _resolve_call(target: str, node_expr: str, rel: str, idx_raw: str | None) -> Path:
    """The "(...)" form's actual resolved path — a file for a bare "()"
    on a `Single` node or a "()[i,j,...]" on an `Array` node, a directory
    otherwise. Callers decide whether to keep a resolved file as-is
    (`resolve_file`, for `vim`) or collapse it to its parent
    (`resolve()`, for `sh`/`free`, which always need a directory)."""
    node_expr = node_expr.strip()
    rel = rel.strip()
    if not node_expr:
        raise TopologyValidationError(
            f"empty node path before '(' in {target!r} — if this came "
            "from an unquoted '~/...', your shell tilde-expanded it "
            "before fatass saw it; quote it or use '~.' instead"
        )
    node_path = expand(node_expr)
    _list_path, chain_index, _suffix = _split_index(node_path)

    if idx_raw is not None:
        if rel != "":
            raise TopologyValidationError(
                f"can't combine an explicit path with an array index in {target!r}"
            )
        if chain_index is not None:
            raise TopologyValidationError(
                f"can't combine a Chain index with an array index directly in "
                f"{target!r} — index the Array after resolving the Chain "
                f"item's own node, e.g. 'members[i].array_field()[j,k]'"
            )
        node_cls = _import_node(node_path)
        if not issubclass(node_cls, Array):
            raise TopologyValidationError(
                f"{node_path!r} is not an Array, can't be indexed with [...]"
            )
        index = _parse_array_index(idx_raw, target)
        return node_cls._file_path(index)

    base = _assets_base(node_path)

    if rel == "":
        # Bare "()" — home dir, except a Single node's own sugar: it
        # resolves straight to its one managed file instead. Only for a
        # plain node — the root sentinel and a Chain-indexed item have no
        # single class of their own to consult here. `_assets_base` above
        # already confirmed a real node exists at this path; any failure
        # actually importing its class past that point (unusual — a
        # broken class file, or a test double with no real package on
        # disk) just means "can't confirm it's a Single", not "no such
        # node", so it falls back to the plain home-dir behavior below.
        if node_path != ROOT and chain_index is None:
            try:
                node_cls = _import_node(node_path)
            except Exception:
                node_cls = None
            if node_cls is not None and issubclass(node_cls, Single):
                return node_cls._file_path()
        return base

    if rel in _HOME_ROOT_MARKERS:
        return base
    return base / rel


def resolve(target: str) -> Path:
    """Resolve a CLI target string — shared by `sh` and `free` — to a
    directory:

    - "node1.node2" -> the node's own directory under fatass/topology/
      (its own <name>.py, __init__.py, transform files, ...).
    - "transform@node1.node2" -> that node's own directory too, since a
      transform file now sits directly in it (no separate transforms/
      subdirectory) — the agent sees the whole node, not an isolated
      transform-only view.
    - "node1.node2(rel/path)" -> a path under the node's home/ assets
      directory ("()", "(.)", or "(./)" for the assets directory itself)
      — uniform across every Node subclass. A path naming a file
      resolves to that file's parent directory, so the file itself can be
      referenced bare wherever the resolved directory is used.
    - "node1.node2()" (bare, empty parens) on a `Single` node is sugar
      for that node's one managed file (still collapsed to its parent
      directory here, same as any other file — use `resolve_file` to keep
      the file itself); on every other node class it's the home dir
      itself, same as "(.)" — no behavioral difference except for Single.
    - "node1.node2()[i,j,...]" on an `Array` node resolves to the file at
      that index (collapsed to its parent directory here too).

    The node-path portion of the "(...)" and "@" forms may contain
    exactly one `name[N]`/`name[*]` indexed segment into a `Chain` (e.g.
    "members[2](rel/path)", "transform@members[*].info") — see
    `fatass.core.transform._split_index`/`_resolve_owning_node`. `[*]`
    means the list's current tail. For the "(...)" form this resolves to
    that specific item's (or schema child's) own home/ directory instead
    of the list's dummy head (the Single/Array empty-call sugar above
    doesn't apply to an indexed item — index it, then call the resolved
    schema child's own node, e.g. "members[2].single_field()"). For the
    "@" form the index is still bounds-checked, but the returned
    directory is always the shared, real topology directory (a schema
    child's transform file is the same file for every item) — see
    `_indexed_topology_dir`. The bare (no "(", no "@") form has no
    per-item topology directory to resolve to at all (only real, declared
    nodes have one) and rejects an indexed target outright.

    Every node-path portion above is first expanded relative to the
    current node (see fatass.resolve.cwd.expand) — FATASS_NODE from the dotenv
    file is prefixed on, "." /".."/etc. navigate from it, and a leading
    "~" ignores it for an absolute path. A node-path portion that expands
    to ROOT ("~", the true topology root — no FATASS_NODE set, or an
    explicit "~") maps to the topology/home root directory itself for
    the plain and "(...)" forms; "transform@~..." is rejected, since the
    root isn't a node and has no transforms of its own.

    The node-path portion before the first "(" must be non-empty — a
    target that starts with "(" (e.g. an unquoted "~/rel/path" that a
    shell tilde-expanded into an absolute filesystem path before fatass
    ever saw it, stripping the leading "~" entirely) is rejected rather
    than silently resolving against the current node, which is what an
    empty node-path expression would otherwise do. Use "~()" (empty
    parens) or "~(.)" for the topology/home root's assets directory
    itself.
    """
    if "@" in target:
        transform_name, node_expr = target.split("@", 1)
        node_path = expand(node_expr)
        if node_path == ROOT:
            raise TopologyValidationError(
                "'~' (the topology root) isn't a node and has no transforms"
            )
        _list_path, index, _suffix = _split_index(node_path)
        if index is None:
            real_node_path = node_path
            if not _node_dir(real_node_path).is_dir():
                raise TopologyValidationError(f"no node at {node_path!r}")
            node_dir = _node_dir(real_node_path)
        else:
            node_dir = _indexed_topology_dir(node_path)
        if not (node_dir / f"{transform_name}.py").is_file():
            raise TopologyValidationError(
                f"no transform named {transform_name!r} under {node_path!r}"
            )
        return node_dir

    match = _CALL_PATTERN.match(target)
    if match:
        path = _resolve_call(target, match.group("node"), match.group("rel"), match.group("idx"))
        return path if path.is_dir() else path.parent

    node_path = expand(target)
    if node_path == ROOT:
        return scaffold._TOPOLOGY_ROOT
    _list_path, index, _suffix = _split_index(node_path)
    if index is not None:
        raise TopologyValidationError(
            f"{target!r}: an indexed item has no topology directory of its "
            f"own (only real, declared nodes do) — use "
            f"'{node_path}(rel/path)' for its home/ content, or "
            f"'transform@{node_path}' for a schema child's transform file"
        )
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")
    return node_dir


def _indexed_topology_dir(node_path: str) -> Path:
    """`_node_dir(...)` of the *real*, index-independent topology
    directory for an indexed `node_path` — a schema child's code is
    shared by every item, so `transform@members[2].info` opens the same
    file `transform@members.info` would; the index is still
    bounds-checked via `_resolve_owning_node` for a clean error, just not
    reflected in the returned path."""
    _owning_cls, discovery_path, _cache_key_prefix = _resolve_owning_node(node_path)
    return _node_dir(discovery_path)


def resolve_file(target: str) -> Path:
    """Resolve a CLI target string — for `vim` — to an actual openable
    file, using the same "node1.node2" / "transform@node1.node2" /
    "node1.node2(rel/path)" grammar as `resolve()` above. `resolve()` always
    returns a directory (a cwd for `sh`/`free`), collapsing a "(...)" file
    target to its parent; this instead keeps the file itself:

    - "node1.node2" -> the node's own <name>.py class file.
    - "transform@node1.node2" -> that transform's own .py file.
    - "node1.node2(rel/path)" -> that path under the node's home/ assets
      directory ("()", "(.)", or "(./)" names the assets directory
      itself, opened as-is — vim browses a directory fine). Unlike the
      plain/"@" forms, the file need not already exist here: vim creates
      it on save, same as running `vim newfile.txt` at a shell.
    - "node1.node2()" on a `Single` node opens its one managed file
      directly; "node1.node2()[i,j,...]" on an `Array` node opens the
      file at that index.

    As in `resolve()`, the node-path portion before the first "(" must be
    non-empty (see there for why — an unquoted "~/..." can get shell
    tilde-expanded before fatass sees it). Also as in `resolve()`, the
    "(...)" and "@" forms accept one indexed segment (`members[2]`,
    `members[*]`); the bare form rejects one outright, same reasoning.
    """
    if "@" in target:
        transform_name, node_expr = target.split("@", 1)
        node_path = expand(node_expr)
        if node_path == ROOT:
            raise TopologyValidationError(
                "'~' (the topology root) isn't a node and has no transforms"
            )
        _list_path, index, _suffix = _split_index(node_path)
        node_dir = _node_dir(node_path) if index is None else _indexed_topology_dir(node_path)
        transform_file = node_dir / f"{transform_name}.py"
        if not transform_file.is_file():
            raise TopologyValidationError(
                f"no transform named {transform_name!r} under {node_path!r}"
            )
        return transform_file

    match = _CALL_PATTERN.match(target)
    if match:
        return _resolve_call(target, match.group("node"), match.group("rel"), match.group("idx"))

    node_path = expand(target)
    if node_path == ROOT:
        raise TopologyValidationError(
            "'~' (the topology root) isn't a node and has no class file"
        )
    _list_path, index, _suffix = _split_index(node_path)
    if index is not None:
        raise TopologyValidationError(
            f"{target!r}: an indexed item has no class file of its own "
            f"(only real, declared nodes do) — use '{node_path}(rel/path)' "
            f"for its home/ content, or 'transform@{node_path}' for a "
            f"schema child's transform file"
        )
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")
    file_stem = node_path.rsplit(".", 1)[-1]
    return node_dir / f"{file_stem}.py"
