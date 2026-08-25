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
from .node import Node
from .node_list import NodeList

_CACHE_PATH = REPO_ROOT / ".fatass" / "cache.json"

_INDEX_SEGMENT = re.compile(r"^(\w+)\[(\d+)\]$")


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


def _split_index(node_path: str) -> tuple[str, int | None, str]:
    """Split a node path with at most one `name[N]` segment (e.g.
    "members[2].info") into (list_node_path, index, suffix) — here
    ("members", 2, "info"). No bracket anywhere returns (node_path, None,
    "") unchanged. More than one indexed segment isn't supported (nested
    NodeLists aren't part of this design)."""
    parts = node_path.split(".")
    matches = [(i, m) for i, part in enumerate(parts) if (m := _INDEX_SEGMENT.match(part))]
    if not matches:
        return node_path, None, ""
    if len(matches) > 1:
        raise ValueError(f"{node_path!r} has more than one indexed segment")

    i, m = matches[0]
    list_node_path = ".".join(parts[: i] + [m.group(1)])
    index = int(m.group(2))
    suffix = ".".join(parts[i + 1 :])
    return list_node_path, index, suffix


def _resolve_owning_node(node_path: str) -> tuple[type[Node], str, str]:
    """(owning_node_class, discovery_path, cache_key_prefix) for
    `node_path` — plain (no `[N]`) or indexed into a `NodeList`.

    `discovery_path` is always the *real* topology path (e.g.
    "members.info"), since `discover()` reflects on that node's own real
    package directory, which is the same regardless of which item is
    being addressed. `cache_key_prefix` bakes the index in
    ("members[2].info") so different items never share a cache entry.
    `owning_node_class` is the class actually passed to `_call()` — for
    an indexed target this is the dynamically-derived, depth-scoped class
    from `NodeList.__getitem__`/`_NodeListItem.__getattr__`, not the
    literal (dummy-head) schema class `_import_node` would otherwise
    return."""
    list_node_path, index, suffix = _split_index(node_path)
    if index is None:
        return _import_node(node_path), node_path, node_path

    list_cls = _import_node(list_node_path)
    if not issubclass(list_cls, NodeList):
        raise TopologyValidationError(
            f"{list_node_path!r} is not a NodeList, can't be indexed"
        )

    item = list_cls()[index]  # bounds-checked, raises TopologyValidationError
    if not suffix:
        raise TopologyValidationError(
            f"{list_node_path}[{index}] needs a schema child, e.g. "
            f"{list_node_path}[{index}].<name> — the list node itself has "
            f"no transforms of its own"
        )

    node_cls = item
    for name in suffix.split("."):
        node_cls = getattr(node_cls, name)  # first hop: NodeListItem.__getattr__

    discovery_path = f"{list_node_path}.{suffix}"
    cache_key_prefix = f"{list_node_path}[{index}].{suffix}"
    return node_cls, discovery_path, cache_key_prefix


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


def _call(owning_node: type[Node], spec: TransformSpec, context: dict[str, Any]) -> None:
    for dep_cls in spec.dependencies.values():
        validate_node(dep_cls)

    kwargs = {name: dep_cls() for name, dep_cls in spec.dependencies.items()}
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
    one indexed into a `NodeList` (e.g. "members[2].info") — see
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
    indexed into a `NodeList` (e.g. "members[2].info") — see
    `_resolve_owning_node`."""
    owning_node, discovery_path, _cache_key_prefix = _resolve_owning_node(node_path)
    validate_node(owning_node)

    specs = [s for s in discover(discovery_path) if s.name == transform_name]
    if not specs:
        raise ValueError(f"no transform named {transform_name!r} under {node_path}")
    spec = specs[0]

    _call(owning_node, spec, _coerce_context(spec, context))
