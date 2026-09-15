import re
from pathlib import Path

from ..node.array import Array
from ..node.single import Single
from ..core.transform import _has_index, _import_node, _resolve_owning_node, resolve_indexed_assets_dir
from ..errors import TopologyValidationError
from ..signature import SIMPLE_TYPED, _split_type_suffix, pathed_signature, validate_node_signature
from ..topology_ops import scaffold
from ..topology_ops.scaffold import _assets_dir, _node_dir
from .cwd import ROOT, expand

_HOME_ROOT_MARKERS = (".", "./")
"""A non-empty `rel` after "/" that still means "the home dir itself"
(an explicit escape hatch — unlike a bare trailing "/", this never
triggers the Single/Array empty-slash sugar below)."""

_ARRAY_INDEX_SUFFIX = re.compile(r"^(?P<rel>.*?)\[(?P<idx>[^\[\]]*)\]$")
""""rel/path[i,j,...]" — an Array index glued onto the very end of a
home-dir target's "rel" portion, anchored at the end of the string (`$`)
so a genuine relative path that merely contains "[...]" somewhere in the
middle is never mistaken for one."""


def _split_transform_ref(node_expr: str) -> tuple[str, str] | None:
    """If `node_expr`'s last dotted segment starts lowercase, it's a
    transform-file reference (`Node.Path.transformName`) rather than a
    plain node path — every real node-path segment is enforced
    PascalCase by `cwd.expand`, so a lowercase leading letter is
    unambiguous proof of transform-name intent (the same heuristic
    `commands._targets._looks_like_transform_target` uses for the
    separate create/touch/modify/apply transform-target grammar).
    Returns (node_part, transform_name), or None if `node_expr` is a
    plain node path."""
    node_part, sep, last = node_expr.rpartition(".")
    if sep and last and last[0].islower():
        return node_part, last
    return None


def is_raw_target(stripped: str) -> bool:
    """True if `stripped` (a target already stripped of any trailing
    "<NodeType(args)>" signature assertion) is a home-dir ("/") or
    transform-file (dotted, lowerCamelCase-last-segment) target rather
    than a plain node path — see `resolve()`. Exposed for `ls`, which
    needs the same distinction to decide between a signature listing and
    a raw directory listing."""
    return "/" in stripped or _split_transform_ref(stripped) is not None


def _parse_array_index(raw: str, target: str) -> tuple[int, ...]:
    try:
        return tuple(int(part.strip()) for part in raw.split(","))
    except ValueError:
        raise TopologyValidationError(
            f"invalid index {raw!r} in {target!r} — expected e.g. '[0,1,1]'"
        ) from None


def _assets_base(node_path: str) -> Path:
    """home/ directory for `node_path` — the true root sentinel, a plain
    node, or one indexed into a Chain/Dictionary (`_has_index`/
    `resolve_indexed_assets_dir`, see `fatass.core.transform`). Shared by
    the "(...)" content form and the empty-"()" non-sugar case."""
    if node_path == ROOT:
        return scaffold._HOME_ROOT
    if not _has_index(node_path):
        if not _node_dir(node_path).is_dir():
            raise TopologyValidationError(f"no node at {node_path!r}")
        return _assets_dir(node_path)
    return resolve_indexed_assets_dir(node_path)


def _resolve_call(target: str, node_expr: str, rest: str) -> Path:
    """The "/" form's actual resolved path — a file for a bare trailing
    "/" on a `Single` node or a "/[i,j,...]" on an `Array` node, a
    directory otherwise. Callers decide whether to keep a resolved file
    as-is (`resolve_file`, for `vim`) or collapse it to its parent
    (`resolve()`, for `sh`/`free`, which always need a directory)."""
    node_expr = node_expr.strip()
    if not node_expr:
        raise TopologyValidationError(
            f"empty node path before '/' in {target!r} — write "
            "\"@/...\" for the topology root's own assets directory "
            "instead of a bare \"/...\""
        )
    node_path = expand(node_expr)

    idx_match = _ARRAY_INDEX_SUFFIX.match(rest)
    rel = (idx_match.group("rel") if idx_match else rest).strip()
    idx_raw = idx_match.group("idx") if idx_match else None

    if idx_raw is not None:
        if rel != "":
            raise TopologyValidationError(
                f"can't combine an explicit path with an array index in {target!r}"
            )
        if _has_index(node_path):
            raise TopologyValidationError(
                f"can't combine a Chain/Dictionary index with an array index "
                f"directly in {target!r} — index the Array after resolving "
                f"the Chain/Dictionary item's own node, e.g. "
                f"'Members[i].ArrayField/[j,k]'"
            )
        node_cls = _import_node(node_path)
        if not issubclass(node_cls, Array):
            raise TopologyValidationError(
                f"{pathed_signature(node_path, SIMPLE_TYPED, max_depth=0)} "
                f"is not an Array, can't be indexed with [...]"
            )
        index = _parse_array_index(idx_raw, target)
        return node_cls._file_path(index)

    base = _assets_base(node_path)

    if rel == "":
        # Bare "()" — home dir, except a Single node's own sugar: it
        # resolves straight to its one managed file instead. Only for a
        # plain node — the root sentinel and a Chain/Dictionary-indexed
        # item have no single class of their own to consult here.
        # `_assets_base` above already confirmed a real node exists at
        # this path; any failure actually importing its class past that
        # point (unusual — a broken class file, or a test double with no
        # real package on disk) just means "can't confirm it's a
        # Single", not "no such node", so it falls back to the plain
        # home-dir behavior below.
        if node_path != ROOT and not _has_index(node_path):
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

    - "Node1.Node2" -> the node's own directory under fatass/topology/
      (its own <name>.py, __init__.py, transform files, ...).
    - "Node1.Node2.transformName" -> that node's own directory too, since
      a transform file sits directly in it (no separate transforms/
      subdirectory) — the agent sees the whole node, not an isolated
      transform-only view. The dotted last segment's lowercase leading
      letter is what marks it as a transform name rather than a child
      node (every real node-path segment is enforced PascalCase).
    - "Node1.Node2/rel/path" -> a path under the node's home/ assets
      directory ("/", "/.", or "/./" for the assets directory itself) —
      uniform across every Node subclass. A path naming a file resolves
      to that file's parent directory, so the file itself can be
      referenced bare wherever the resolved directory is used.
    - "Node1.Node2/" (bare, nothing after the slash) on a `Single` node
      is sugar for that node's one managed file (still collapsed to its
      parent directory here, same as any other file — use `resolve_file`
      to keep the file itself); on every other node class it's the home
      dir itself, same as "/." — no behavioral difference except for
      Single.
    - "Node1.Node2/[i,j,...]" on an `Array` node resolves to the file at
      that index (collapsed to its parent directory here too).

    The node-path portion of the "/" and dotted-transform forms may
    contain any number of `Name[N]`/`Name[*]`/`Name[key]` indexed
    segments into a `Chain`/`Dictionary`, anywhere along the path — e.g.
    "Members[2]/rel/path", "Members[*].info", or (nesting a `Chain`
    inside a `Dictionary` entry) "Courses[eiki].Lecture[0].Exercise" —
    see `fatass.core.transform._parse_indexed_path`/`_resolve_owning_node`.
    `[*]` means a `Chain`'s current tail. For the "/" form this resolves
    to that specific item's (or schema child's) own home/ directory
    instead of the list's dummy head (the Single/Array empty-slash sugar
    above doesn't apply to an indexed item — index it, then call the
    resolved schema child's own node, e.g. "Members[2].SingleField/").
    For the dotted-transform form every index is still bounds/existence-
    checked, but the returned directory is always the shared, real
    topology directory (a schema child's transform file is the same file
    for every item) — see `_indexed_topology_dir`. The bare (no "/", no
    dotted transform) form has no per-item topology directory to resolve
    to at all (only real, declared nodes have one) and rejects an
    indexed target outright.

    Every node-path portion above is first expanded relative to the
    current node (see fatass.resolve.cwd.expand) — FATASS_NODE from the dotenv
    file is prefixed on, "." /".."/etc. navigate from it, and a leading
    "@" ignores it for an absolute path. A node-path portion that expands
    to ROOT ("@", the true topology root — no FATASS_NODE set, or an
    explicit "@") maps to the topology/home root directory itself for
    the plain and "/" forms; "@.transformName" is rejected, since the
    root isn't a node and has no transforms of its own.

    The node-path portion before the first "/" must be non-empty — a
    target that starts with "/" is rejected rather than silently
    resolving against the current node, which is what an empty node-
    path expression would otherwise do. Use "@/" (bare trailing slash)
    or "@/." for the topology/home root's assets directory itself.

    The bare and dotted-transform forms may also carry a trailing
    "<NodeType(args)>" signature assertion (e.g. "Node1.Node2<Chain>",
    "Node1.Node2.transformName<Chain>") — see
    `fatass.signature.validate_node_signature` — checked against the
    node the rest of the target already resolved to, non-indexed targets
    only (an indexed one is topologically the same schema node
    regardless of index, but there's no single obvious node among its
    several possible schema children to validate a bare index against,
    so it's skipped rather than guessed at). Not supported on the "/"
    form at all.
    """
    stripped, type_name, expected_sig = _split_type_suffix(target)

    if "/" in stripped:
        node_expr, _, rest = stripped.partition("/")
        path = _resolve_call(stripped, node_expr, rest)
        return path if path.is_dir() else path.parent

    transform_ref = _split_transform_ref(stripped)
    if transform_ref is not None:
        node_part, transform_name = transform_ref
        node_path = expand(node_part)
        if node_path == ROOT:
            raise TopologyValidationError(
                "'@' (the topology root) isn't a node and has no transforms"
            )
        if not _has_index(node_path):
            if not _node_dir(node_path).is_dir():
                raise TopologyValidationError(f"no node at {node_path!r}")
            node_dir = _node_dir(node_path)
        else:
            node_dir = _indexed_topology_dir(node_path)
        if not (node_dir / f"{transform_name}.py").is_file():
            raise TopologyValidationError(
                f"no transform named {transform_name!r} under {node_path!r}"
            )
        # Suffix validation only for a non-indexed target — an indexed
        # one (`Members[2].info`) is topologically the same schema node
        # regardless of index (see the topological invariant discussed
        # throughout `fatass.node.chain`), but pinning down exactly which
        # of the list/dict's several possible schema children to
        # validate against would need its own dedicated resolution;
        # skipped here rather than guessed at.
        if type_name is not None and not _has_index(node_path):
            validate_node_signature(node_path, type_name, expected_sig, target)
        return node_dir

    node_path = expand(stripped)
    if node_path == ROOT:
        return scaffold._TOPOLOGY_ROOT
    if _has_index(node_path):
        raise TopologyValidationError(
            f"{target!r}: an indexed item has no topology directory of its "
            f"own (only real, declared nodes do) — use "
            f"'{node_path}/rel/path' for its home/ content, or "
            f"'{node_path}.transformName' for a schema child's transform file"
        )
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")
    if type_name is not None:
        validate_node_signature(node_path, type_name, expected_sig, target)
    return node_dir


def _indexed_topology_dir(node_path: str) -> Path:
    """`_node_dir(...)` of the *real*, index-independent topology
    directory for an indexed `node_path` — a schema child's code is
    shared by every item, so `Members[2].info` opens the same file
    `Members.info` would; the index is still bounds-checked via
    `_resolve_owning_node` for a clean error, just not reflected in the
    returned path."""
    _owning_cls, discovery_path, _cache_key_prefix = _resolve_owning_node(node_path)
    return _node_dir(discovery_path)


def resolve_file(target: str) -> Path:
    """Resolve a CLI target string — for `vim` — to an actual openable
    file, using the same "Node1.Node2" / "Node1.Node2.transformName" /
    "Node1.Node2/rel/path" grammar as `resolve()` above. `resolve()`
    always returns a directory (a cwd for `sh`/`free`), collapsing a "/"
    file target to its parent; this instead keeps the file itself:

    - "Node1.Node2" -> the node's own <name>.py class file.
    - "Node1.Node2.transformName" -> that transform's own .py file.
    - "Node1.Node2/rel/path" -> that path under the node's home/ assets
      directory ("/", "/.", or "/./" names the assets directory itself,
      opened as-is — vim browses a directory fine). Unlike the plain/
      dotted-transform forms, the file need not already exist here: vim
      creates it on save, same as running `vim newfile.txt` at a shell.
    - "Node1.Node2/" on a `Single` node opens its one managed file
      directly; "Node1.Node2/[i,j,...]" on an `Array` node opens the
      file at that index.

    As in `resolve()`, the node-path portion before the first "/" must be
    non-empty (see there for why). Also as in `resolve()`, the "/" and
    dotted-transform forms accept one indexed segment (`Members[2]`,
    `Members[*]`); the bare form rejects one outright, same reasoning.

    The bare and dotted-transform forms also accept the same optional
    trailing "<NodeType(args)>" signature assertion `resolve()` does
    (non-indexed targets only, not supported on the "/" form) — see that
    function's own docstring.
    """
    stripped, type_name, expected_sig = _split_type_suffix(target)

    if "/" in stripped:
        node_expr, _, rest = stripped.partition("/")
        return _resolve_call(stripped, node_expr, rest)

    transform_ref = _split_transform_ref(stripped)
    if transform_ref is not None:
        node_part, transform_name = transform_ref
        node_path = expand(node_part)
        if node_path == ROOT:
            raise TopologyValidationError(
                "'@' (the topology root) isn't a node and has no transforms"
            )
        has_index = _has_index(node_path)
        node_dir = _node_dir(node_path) if not has_index else _indexed_topology_dir(node_path)
        transform_file = node_dir / f"{transform_name}.py"
        if not transform_file.is_file():
            raise TopologyValidationError(
                f"no transform named {transform_name!r} under {node_path!r}"
            )
        if type_name is not None and not has_index:
            validate_node_signature(node_path, type_name, expected_sig, target)
        return transform_file

    node_path = expand(stripped)
    if node_path == ROOT:
        raise TopologyValidationError(
            "'@' (the topology root) isn't a node and has no class file"
        )
    if _has_index(node_path):
        raise TopologyValidationError(
            f"{target!r}: an indexed item has no class file of its own "
            f"(only real, declared nodes do) — use '{node_path}/rel/path' "
            f"for its home/ content, or '{node_path}.transformName' for a "
            f"schema child's transform file"
        )
    node_dir = _node_dir(node_path)
    if not node_dir.is_dir():
        raise TopologyValidationError(f"no node at {node_path!r}")
    if type_name is not None:
        validate_node_signature(node_path, type_name, expected_sig, target)
    file_stem = node_path.rsplit(".", 1)[-1]
    return node_dir / f"{file_stem}.py"
