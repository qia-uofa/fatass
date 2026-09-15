import dataclasses
import hashlib
import importlib
import inspect
import json
import re
import typing
from pathlib import Path
from typing import Any, Callable

from .._internal.naming import pascal_case
from .._internal.paths import REPO_ROOT
from ..errors import TopologyValidationError
from .free import _current_node
from ..node.node import Node
from ..node.chain import Chain
from ..node.dictionary import Dictionary

_CACHE_PATH = REPO_ROOT / ".fatass" / "cache.json"

_INDEX_SEGMENT = re.compile(r"^(\w+)\[([^\[\]]+)\]$")


@dataclasses.dataclass
class TransformSpec:
    name: str
    func: Callable
    dependencies: dict[str, type]
    context_params: dict[str, inspect.Parameter]


def _module_name(node_path: str) -> str:
    # CLI/API node paths use "." throughout (node1.node2), matching Python
    # module addressing directly — no separate slash-path translation.
    return "fatass.topology." + node_path


def _import_node(node_path: str) -> type[Node]:
    module_name = _module_name(node_path)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise  # a real bug inside some module along the way, not "no such node"
        raise TopologyValidationError(
            f"no node at {node_path!r} (no such module {module_name})"
        ) from exc
    class_name = pascal_case(node_path.rsplit(".", 1)[-1])
    node_cls = getattr(module, class_name, None)
    if node_cls is None:
        raise TopologyValidationError(
            f"{module.__name__} does not define a {class_name} class"
        )
    return node_cls


def validate_node(node_cls: type[Node]) -> None:
    assets_dir = node_cls._assets_dir()
    if not assets_dir.is_dir():
        raise TopologyValidationError(
            f"{node_cls._topology_path()} has no corresponding home/ "
            f"directory (expected {assets_dir})"
        )


def _has_index(node_path: str) -> bool:
    """True if `node_path` contains at least one `name[...]` indexed
    segment anywhere — a cheap presence check (`[` never appears in an
    ordinary node-path segment — PascalCase-enforced, and a `Dictionary`
    key can't contain one either, see `node.dictionary._validate_key`)
    for a caller that only needs to decide whether to route through
    indexed resolution at all, not the parsed details themselves (used
    throughout `resolve.targets`, which doesn't need to know HOW MANY
    indexed segments there are, just whether there's at least one)."""
    return "[" in node_path


def _parse_indexed_path(node_path: str) -> list[tuple[str, str | None]]:
    """Split `node_path` into its dot-separated segments, each already
    split into `(name, raw_index)` — `raw_index` is a segment's own
    bracket text (e.g. "2", "*", "alice"), untyped — deliberately: at
    parse time nothing has imported anything yet to know whether a given
    segment indexes a `Chain` (where "2"/"*" need converting to an actual
    int position) or a `Dictionary` (where the text itself already IS
    the key) — that decision belongs to `_index_into`, once each
    segment's own owning class is actually known. `raw_index` is `None`
    for a plain, unindexed segment. Any number of segments may carry
    their own index, anywhere along the path — nesting one collection
    inside another (e.g. "courses[eiki].lecture[0].exercise", a
    `Dictionary` entry's own `Chain` schema child, itself indexed) is
    fully supported; `_resolve_owning_node`/`resolve_indexed_assets_dir`
    walk the segments left to right, indexing into whichever ones carry
    a bracket. Raises `ValueError` if any segment doesn't match the
    `name` / `name[index]` shape."""
    segments = []
    for part in node_path.split("."):
        m = _INDEX_SEGMENT.match(part)
        if m:
            segments.append((m.group(1), m.group(2)))
        elif re.fullmatch(r"\w+", part):
            segments.append((part, None))
        else:
            raise ValueError(f"invalid path segment {part!r} in {node_path!r}")
    return segments


def _index_into(owner_cls: type[Node], raw_index: str, label: str):
    """`raw_index` (one segment's own bracket text) resolved against
    `owner_cls` — a `Chain` (`raw_index` must be a non-negative integer
    literal, or "*" for the current tail) or a `Dictionary` (`raw_index`
    is used as-is, the literal key) — returning `(item, index_repr)`:
    `item` is the `_ChainItem`/`_DictItem` instance (bounds/existence-
    checked, raises `TopologyValidationError` otherwise), and
    `index_repr` is what the cache key/error messages should show (an
    `int` for a `Chain`, the raw string key for a `Dictionary`).
    `owner_cls` not being a `Chain`/`Dictionary` at all is also an error
    here. `label` is the real dotted path up to and including this
    segment's own name, used only to phrase an error message — works
    for a segment at any depth (not just the first), since `owner_cls`
    itself may already be a dynamically-derived, index-scoped class from
    an earlier segment in the same walk."""
    if issubclass(owner_cls, Chain):
        if raw_index == "*":
            length = owner_cls.length()
            if length == 0:
                raise TopologyValidationError(
                    f"{owner_cls._topology_path()} is empty — [*] has no tail to resolve to"
                )
            index = length - 1
        elif raw_index.lstrip("-").isdigit():
            index = int(raw_index)
        else:
            raise TopologyValidationError(
                f"{label}[{raw_index}] isn't a valid Chain index — "
                f"expected a non-negative integer or '*'"
            )
        return owner_cls()[index], index  # bounds-checked, raises TopologyValidationError
    if issubclass(owner_cls, Dictionary):
        return owner_cls()[raw_index], raw_index  # existence-checked, raises TopologyValidationError

    from ..signature import SIMPLE_TYPED, pathed_signature  # local: avoid a cycle (signature imports this module)

    raise TopologyValidationError(
        f"{pathed_signature(owner_cls._topology_path(), SIMPLE_TYPED, max_depth=0)} "
        f"is not a Chain or Dictionary, can't be indexed"
    )


def _walk_indexed_path(node_path: str):
    """Shared walk behind `_resolve_owning_node`/`resolve_indexed_assets_dir`:
    resolves every segment of `node_path` in order, importing the first
    one and `getattr`-chasing (`_ChainItem`/`_DictItem.__getattr__`, or
    `NodeMeta.__getattr__` for a second-plus hop off an already-indexed
    class) every one after it, indexing into a segment wherever it
    carries its own `[...]`. Returns `(resolved, real_path_parts,
    cache_key_parts)` — `resolved` is a class if the path's last segment
    was plain, or a bare `_ChainItem`/`_DictItem` instance if the last
    segment was itself indexed with nothing after it (the two callers
    tell these apart with `isinstance(resolved, type)`); the two part
    lists are the real (index-free) and cache-key (index-baked-in)
    dotted paths, segment by segment, for the caller to join as needed."""
    segments = _parse_indexed_path(node_path)
    resolved = None
    real_path_parts: list[str] = []
    cache_key_parts: list[str] = []
    for name, raw_index in segments:
        real_path_parts.append(name)
        resolved = _import_node(".".join(real_path_parts)) if resolved is None else getattr(resolved, name)
        cache_key_parts.append(name)
        if raw_index is not None:
            item, index_repr = _index_into(resolved, raw_index, ".".join(real_path_parts))
            resolved = item
            cache_key_parts[-1] = f"{name}[{index_repr}]"
    return resolved, real_path_parts, cache_key_parts


def _resolve_owning_node(node_path: str) -> tuple[type[Node], str, str]:
    """(owning_node_class, discovery_path, cache_key_prefix) for
    `node_path` — plain (no `[...]` anywhere) or indexed into one or more
    nested `Chain`/`Dictionary` collections along the way (e.g.
    "courses[eiki].lecture[0].exercise").

    `discovery_path` is always the *real* topology path (e.g.
    "members.info"), since `discover()` reflects on that node's own real
    package directory, which is the same regardless of which item is
    being addressed. `cache_key_prefix` bakes every index/key in along
    the way ("members[2].info"/"courses[eiki].lecture[0].exercise") so
    different items never share a cache entry. `owning_node_class` is the
    class actually passed to `_call()` — for an indexed target this is
    the dynamically-derived, depth-scoped class from `Chain.__getitem__`/
    `_ChainItem.__getattr__` (or `Dictionary`/`_DictItem`'s own
    equivalents), not the literal (dummy-head) schema class
    `_import_node` would otherwise return."""
    if not _has_index(node_path):
        return _import_node(node_path), node_path, node_path

    resolved, real_path_parts, cache_key_parts = _walk_indexed_path(node_path)
    if not isinstance(resolved, type):
        # The last segment was itself indexed, with nothing after it --
        # a bare list/dict item, which has no transform of its own.
        cache_key_path = ".".join(cache_key_parts)
        raise TopologyValidationError(
            f"{cache_key_path} needs a schema child, e.g. "
            f"{cache_key_path}.<name> — the list/dict node itself has "
            f"no transforms of its own"
        )

    discovery_path = ".".join(real_path_parts)
    cache_key_prefix = ".".join(cache_key_parts)
    return resolved, discovery_path, cache_key_prefix


def resolve_indexed_assets_dir(node_path: str) -> Path:
    """`home/` directory for an indexed `node_path` — like
    `_resolve_owning_node`, but for `sh`/`free`/`ls`/`vim`'s "/" target
    form rather than `run`/`apply`/`build`'s transform-scoping: a bare
    indexed item at the very end (e.g. "members[2]"/"members[alice]", no
    schema-child suffix) is valid here — it resolves straight to that
    item's own `._assets_dir()` (`.entry` for a leaf list/dict) — whereas
    `_resolve_owning_node` requires a schema child after the last index,
    since a bare item has no *transform* to run. Any earlier segment may
    still carry its own index either way (nesting), same as
    `_resolve_owning_node`."""
    if not _has_index(node_path):
        raise ValueError(f"{node_path!r} has no indexed segment")

    resolved, _real_path_parts, _cache_key_parts = _walk_indexed_path(node_path)
    return resolved._assets_dir()


def _load_transform_function(node_path: str, stem: str):
    module_name = f"{_module_name(node_path)}.{stem}"
    module = importlib.import_module(module_name)
    return getattr(module, stem, None)


def discover(node_path: str) -> list[TransformSpec]:
    """Every transform sitting directly in node_path's own package
    directory — one function per file, named the same as its module stem.
    A transform needs no Node-typed parameter: a function with none still
    counts, just with an empty `dependencies` dict (see build_graph()'s
    "None" node for how that's drawn)."""
    module_name = _module_name(node_path)
    try:
        package = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return []

    own_file_stem = node_path.rsplit(".", 1)[-1]
    specs = []
    for path in package.__path__:
        for file in sorted(Path(path).glob("*.py")):
            if file.stem in ("__init__", own_file_stem):
                continue
            func = _load_transform_function(node_path, file.stem)
            if func is None or not callable(func):
                continue
            hints = typing.get_type_hints(func)
            dependencies = {}
            context_params = {}
            for name, param in inspect.signature(func).parameters.items():
                hint = hints.get(name)
                if isinstance(hint, type) and issubclass(hint, Node):
                    dependencies[name] = hint
                else:
                    context_params[name] = param
            specs.append(
                TransformSpec(
                    name=file.stem,
                    func=func,
                    dependencies=dependencies,
                    context_params=context_params,
                )
            )
    return specs


def _hash_dir(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def _input_hash(spec: TransformSpec) -> str:
    parts = sorted(
        (name, _hash_dir(dep_cls._assets_dir()))
        for name, dep_cls in spec.dependencies.items()
    )
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def _load_cache() -> dict:
    if not _CACHE_PATH.exists():
        return {}
    return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


_CACHE_KEY_INDEX = re.compile(r"^(?P<list_path>.+)\[(?P<index>\d+)\]\.")


def invalidate_index_cache(list_path: str, from_index: int) -> int:
    """Drop every cache entry keyed to `list_path[i]...` for `i >=
    from_index` — called by `Chain.insert`/`.pop` whenever they shift
    existing items to a different index (never for a plain tail
    push/pop, which doesn't move anything).

    A cache entry's key bakes in a purely positional index
    ("members[2].info.transforms.build") tied to `_input_hash()` of that
    transform's *external* dependencies — never to the item's own
    content. After a shift, index `i`'s directory holds a *different*
    item than whatever the cache last recorded for that number. Since
    many items commonly share identical dependencies, a stale entry can
    coincidentally still match the new item's input hash — a false cache
    hit — which would silently skip ever running that transform for a
    freshly inserted item (its own `.entry`/schema directories would stay
    empty). Deleting the stale entries outright, rather than trying to
    move them, is the safe default: the worst case is one redundant rerun
    per shifted item, not a silently-unpopulated one.

    Returns the number of entries dropped."""
    cache = _load_cache()
    prefix = f"{list_path}["
    to_drop = []
    for key in cache:
        if not key.startswith(prefix):
            continue
        match = _CACHE_KEY_INDEX.match(key)
        if match and match.group("list_path") == list_path and int(match.group("index")) >= from_index:
            to_drop.append(key)
    for key in to_drop:
        del cache[key]
    if to_drop:
        _save_cache(cache)
    return len(to_drop)


_CACHE_KEY_DICT_INDEX = re.compile(r"^(?P<dict_path>.+)\[(?P<key>[^\]]+)\]\.")


def invalidate_dict_key_cache(dict_path: str, key: str) -> int:
    """Drop every cache entry keyed to exactly `dict_path[key]...` —
    called by `Dictionary.pop`. Unlike `invalidate_index_cache`, this is
    never a range: removing one key from a `Dictionary` never changes
    any *other* key's own identity (nothing shifts), so only that one
    key's own stale entries need dropping — guards the same false-
    cache-hit risk `invalidate_index_cache` does, for the one case where
    it can actually arise here: the same key gets `.set()` again later
    with different content than what the cache last recorded for it.

    Returns the number of entries dropped."""
    cache = _load_cache()
    prefix = f"{dict_path}["
    to_drop = []
    for cache_key in cache:
        if not cache_key.startswith(prefix):
            continue
        match = _CACHE_KEY_DICT_INDEX.match(cache_key)
        if match and match.group("dict_path") == dict_path and match.group("key") == key:
            to_drop.append(cache_key)
    for cache_key in to_drop:
        del cache[cache_key]
    if to_drop:
        _save_cache(cache)
    return len(to_drop)


def _resolve_dependency(owning_node: type[Node], dep_cls: type[Node]) -> Node:
    """Normally just `dep_cls()` — the literal, non-indexed class a
    static `from fatass.topology... import X` always gives. But when
    `owning_node` is itself one of `Chain`/`Dictionary`'s dynamically-
    derived per-index schema-child classes (has `_sibling`, see
    `_ChainItem.__getattr__`/`_DictItem.__getattr__`) and `dep_cls`
    names another schema child of that SAME list/dict at the SAME
    depth — a sibling — that literal class would be the wrong one: every
    item's transform would read the shared dummy head instead of its own
    sibling's actual content, no matter which item is running. Detected
    by comparing `dep_cls`'s own real topology path against
    `owning_node`'s owning list/dict's path + one more segment; when it
    matches, resolve through `owning_node._sibling(...)` instead, which
    is index/key-aware. This is what makes a normal `source: Source`-
    style declared dependency usable on a per-item Chain/Dictionary
    schema-child transform (e.g. `init(source)@projects.info`) without
    the caller having to know or care that it's running per-item at
    all — `_index_owner_cls`/`_index_key` are the shared, kind-agnostic
    names both `Chain` and `Dictionary` items stamp."""
    sibling = getattr(owning_node, "_sibling", None)
    if sibling is not None:
        try:
            list_path = owning_node._index_owner_cls()._topology_path()
            dep_path = dep_cls._topology_path()
            prefix = list_path + "."
            if dep_path.startswith(prefix) and "." not in dep_path[len(prefix):]:
                return sibling(dep_path[len(prefix):])()
        except Exception:
            pass
    return dep_cls()


def _call(owning_node: type[Node], spec: TransformSpec, context: dict[str, Any]) -> None:
    for dep_cls in spec.dependencies.values():
        validate_node(dep_cls)

    kwargs = {name: _resolve_dependency(owning_node, dep_cls) for name, dep_cls in spec.dependencies.items()}
    kwargs.update(context)

    token = _current_node.set(owning_node)
    try:
        spec.func(**kwargs)
    finally:
        _current_node.reset(token)


def _run_one(cache_key_prefix: str, owning_node: type[Node], spec: TransformSpec, force: bool) -> bool:
    cache_key = f"{cache_key_prefix}.transforms.{spec.name}"
    input_hash = _input_hash(spec)
    cache = _load_cache()
    if not force and cache.get(cache_key) == input_hash:
        return False  # skipped, cache hit

    _call(owning_node, spec, {})

    cache[cache_key] = input_hash
    _save_cache(cache)
    return True  # ran


def run_transform(node_path: str, transform_name: str | None = None, *, force: bool = False) -> dict[str, bool]:
    """Run one transform (if `transform_name` is given) or every transform
    discovered under `node_path`. `node_path` may be a plain node path or
    one indexed into a `Chain` (e.g. "members[2].info") — see
    `_resolve_owning_node`. Returns {transform_name: ran_bool}."""
    owning_node, discovery_path, cache_key_prefix = _resolve_owning_node(node_path)
    validate_node(owning_node)

    specs = discover(discovery_path)
    if transform_name is not None:
        specs = [s for s in specs if s.name == transform_name]
        if not specs:
            raise ValueError(
                f"no transform named {transform_name!r} under {node_path}"
            )

    return {
        spec.name: _run_one(cache_key_prefix, owning_node, spec, force) for spec in specs
    }


_CONTEXT_COERCERS = {
    str: str,
    int: int,
    float: float,
    bool: lambda v: v.strip().lower() in ("1", "true", "yes", "on"),
}


def _coerce_context(spec: TransformSpec, raw: dict[str, str]) -> dict[str, Any]:
    unknown = set(raw) - set(spec.context_params)
    if unknown:
        raise ValueError(
            f"{spec.name} has no argument(s) named {', '.join(sorted(unknown))} "
            f"(known: {', '.join(sorted(spec.context_params)) or 'none'})"
        )
    hints = typing.get_type_hints(spec.func)
    coerced = {}
    for name, value in raw.items():
        coercer = _CONTEXT_COERCERS.get(hints.get(name), str)
        try:
            coerced[name] = coercer(value)
        except ValueError as exc:
            raise ValueError(f"couldn't parse {name}={value!r}: {exc}") from exc
    return coerced


def apply_transform(node_path: str, transform_name: str, context: dict[str, str]) -> None:
    """Run one transform with explicit context arguments, unconditionally
    (no cache check, no cache write — the cache only represents the
    default-arguments `run_transform` flow; a custom-argument `apply` call
    isn't comparable to it). `node_path` may be a plain node path or one
    indexed into a `Chain` (e.g. "members[2].info") — see
    `_resolve_owning_node`."""
    owning_node, discovery_path, _cache_key_prefix = _resolve_owning_node(node_path)
    validate_node(owning_node)

    specs = [s for s in discover(discovery_path) if s.name == transform_name]
    if not specs:
        raise ValueError(f"no transform named {transform_name!r} under {node_path}")
    spec = specs[0]

    _call(owning_node, spec, _coerce_context(spec, context))
