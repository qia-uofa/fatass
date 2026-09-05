import re

from ..node.chain import Chain
from ..core.transform import _import_node
from ..errors import TopologyValidationError
from ..resolve.cwd import ROOT, expand

_BASE_CLASS_SUFFIX = re.compile(
    r"\((?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\((?P<args>[^()]*)\))?"
    r"(?:,(?P<kwargs>[^()]*))?"
    r"\)$"
)
_TRANSFORM_WITH_DEPS = re.compile(
    r"^(?P<transform>[A-Za-z_][A-Za-z0-9_]*)\((?P<deps>[^()]*)\)@(?P<node>.+)$"
)


def resolve_node_path(raw: str) -> str:
    """Expand a node-path expression relative to the current node (see
    fatass.resolve.cwd.expand — FATASS_NODE from the dotenv file, "."/".."/"~"
    navigation, etc.), rejecting ROOT: every command that takes a
    node.path needs an actual node, not the bare topology root."""
    node_path = expand(raw)
    if node_path == ROOT:
        raise TopologyValidationError(
            f"{raw!r} resolved to the topology root, which isn't a node"
        )
    return node_path


def parse_node_path(path: str) -> tuple[str, str | None]:
    """"."-separated node/transform path, e.g.
    "node1.node2.transforms.synthesize" -> ("node1.node2", "synthesize").
    The node-path half is resolved via resolve_node_path()."""
    parts = path.split(".")
    if len(parts) >= 2 and parts[-2] == "transforms":
        node_path, transform_name = ".".join(parts[:-2]), parts[-1]
    else:
        node_path, transform_name = path, None
    return resolve_node_path(node_path), transform_name


def parse_at_target(target: str) -> tuple[str, str]:
    """<transform>@<node.path> -> (node_path, transform_name). Requires
    the transform half to be present. The node-path half is resolved via
    resolve_node_path()."""
    if "@" not in target:
        raise ValueError(f"expected <transform>@<node>, got {target!r}")
    transform_name, node_path = target.split("@", 1)
    return resolve_node_path(node_path), transform_name


def parse_maybe_at_target(target: str) -> tuple[str, str | None]:
    """Same as parse_at_target, but a bare node path (no "@") is valid too
    — used where a target may name either a node or a transform on one."""
    if "@" in target:
        transform_name, node_path = target.split("@", 1)
        return resolve_node_path(node_path), transform_name
    return resolve_node_path(target), None


def _parse_class_kwargs(raw: str | None, target: str) -> dict[str, tuple]:
    """The "(NodeSubclass,dim=2x2x2)" suffix's legacy extra part — just
    Array's `dim=<int>x<int>x...`, "x"-separated (not comma-separated,
    which would collide with the outer "(NodeSubclass,...)" split)."""
    if not raw:
        return {}
    kwargs: dict[str, tuple] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"invalid class argument {item!r} in {target!r}")
        key, value = item.split("=", 1)
        key, value = key.strip(), value.strip()
        if key == "dim":
            try:
                kwargs[key] = tuple(int(part) for part in value.split("x"))
            except ValueError:
                raise ValueError(
                    f"invalid dim {value!r} in {target!r} — expected e.g. "
                    f"'dim=2x2x2'"
                ) from None
        else:
            raise ValueError(f"unknown class argument {key!r} in {target!r}")
    return kwargs


def _split_top_level(raw: str) -> list[str]:
    """Comma-split `raw`, but not commas nested inside a "[...]" (Array's
    positional `dim` list — see `_parse_subclass_args`)."""
    parts: list[str] = []
    current = ""
    depth = 0
    for ch in raw:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def _parse_subclass_args(raw: str | None, target: str) -> dict[str, tuple]:
    """The "(NodeSubclass(...))" suffix's constructor-style args — e.g.
    "my_node(SingleCsv(field1,field2))" or
    "my_node(ArrayCsv([2,2,4],field1,field2))". A leading "[i,j,...]"
    positional argument is Array's `dim` (its own "x"-separated
    "dim=2x2x2" keyword form still works too, see `_parse_class_kwargs`);
    every remaining positional argument is a field name, collected as
    `fields`."""
    if not raw:
        return {}
    args = _split_top_level(raw)
    kwargs: dict[str, tuple] = {}
    if args and args[0].startswith("[") and args[0].endswith("]"):
        dim_raw = args.pop(0)[1:-1]
        try:
            kwargs["dim"] = tuple(int(part.strip()) for part in dim_raw.split(","))
        except ValueError:
            raise ValueError(
                f"invalid dim {dim_raw!r} in {target!r} — expected e.g. '[2,2,4]'"
            ) from None
    for arg in args:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", arg):
            raise ValueError(f"invalid field name {arg!r} in {target!r}")
    if args:
        kwargs["fields"] = tuple(args)
    return kwargs


def parse_create_target(
    target: str,
) -> tuple[str, str | None, str, list[str], list[tuple[str, str]], dict[str, tuple]]:
    """Same as parse_maybe_at_target, but also accepts:

    - a trailing "(NodeSubclass)" on the target — e.g. "members(Chain)"
      or "build@members(Chain)" — naming the `fatass.<NodeSubclass>`
      base class a newly-created node should subclass instead of the
      default `fatass.Node`. The suffix is only meaningful for creating a
      node, so it's stripped before the rest of the target is parsed.
      Optionally followed by ",<key>=<value>" extra class arguments —
      currently just "dim=<int>x<int>x..." for an Array subclass, e.g.
      "grid(ArrayTxt,dim=2x2x2)" — baked into the generated class as
      `DIM = (2, 2, 2)` (see `scaffold.create_node`'s `class_kwargs`) so
      the node's shape is known immediately, before `on_created()` runs.
    - Or the NodeSubclass itself followed by its own parens of
      constructor-style positional args (see `_parse_subclass_args`) —
      e.g. "my_node(SingleCsv(field1,field2))" bakes `FIELDS = ("field1",
      "field2")` onto the class, written as that Single's header row on
      creation; "my_node(ArrayCsv([2,2,4],field1,field2))" bakes both
      `DIM = (2, 2, 4)` (from the leading "[...]") and the same `FIELDS`,
      written as every one of that Array's files' header row.
    - "<transform>(<dep1>,<dep2>,<name>:<type>,...)@<node.path>" — e.g.
      "build(node1,node2,prompt:str,n:int)@node" — a comma-separated list
      mixing dependency node.paths (bound the same way as `bind`, a
      deterministic operation, not an agent call) with plain typed
      parameters (added as ordinary, import-free parameters with that
      annotation — no default, no binding). An entry containing ":" is a
      plain parameter (name:type); anything else is a dependency
      node.path. Whitespace around each comma-separated entry is
      stripped, so "build(node1, node2)@node" works the same as
      "build(node1,node2)@node". Mutually exclusive with the
      "(NodeSubclass)" suffix (that one only applies to a bare node
      target, this one only to a "<transform>@..." one).

    Returns (node_path, transform_name, base_class, dep_node_paths,
    plain_params, class_kwargs) — the last three always falsy except for
    their own respective forms above. Only used by `create` — every other
    command's targets don't create nodes."""
    deps_match = _TRANSFORM_WITH_DEPS.match(target)
    if deps_match:
        transform_name = deps_match.group("transform")
        dep_paths: list[str] = []
        plain_params: list[tuple[str, str]] = []
        for item in deps_match.group("deps").split(","):
            item = item.strip()
            if not item:
                continue
            if ":" in item:
                name, type_str = item.split(":", 1)
                name, type_str = name.strip(), type_str.strip()
                if not name or not type_str:
                    raise ValueError(f"invalid parameter {item!r} in {target!r}")
                plain_params.append((name, type_str))
            else:
                dep_paths.append(resolve_node_path(item))
        node_path = resolve_node_path(deps_match.group("node"))
        return node_path, transform_name, "Node", dep_paths, plain_params, {}

    match = _BASE_CLASS_SUFFIX.search(target)
    if match:
        base_class = match.group("name")
        class_kwargs = {
            **_parse_subclass_args(match.group("args"), target),
            **_parse_class_kwargs(match.group("kwargs"), target),
        }
        target = target[: match.start()]
    else:
        base_class = "Node"
        class_kwargs = {}
    node_path, transform_name = parse_maybe_at_target(target)
    return node_path, transform_name, base_class, [], [], class_kwargs


def resolve_move_target(raw_new: str, old_path: str) -> str:
    """`move`/`copy`'s destination argument, with a trailing "*" segment
    substituted for `old_path`'s own leaf name — e.g. "node2.*" (with
    `old_path` "node1") resolves the same as "node2.node1": reparent
    under node2, keeping the same name, mirroring Unix `mv file dir/`
    ("move node1 into node2, same name"). A bare "*" alone means "same
    name, at the current node" — resolved from whatever `raw_new` would
    otherwise expand from (still goes through `resolve_node_path`, so
    "."/".."/"~" navigation before the "*" still works, e.g.
    "node2..*"). Only the trailing segment may be "*" — a literal node
    named "*" isn't otherwise expressible (not a valid Python
    identifier), so this substitution is unambiguous."""
    if raw_new == "*" or raw_new.endswith(".*"):
        stem = old_path.rsplit(".", 1)[-1]
        raw_new = stem if raw_new == "*" else f"{raw_new[:-1]}{stem}"
    return resolve_node_path(raw_new)


def resolve_chain(raw: str) -> type[Chain]:
    """`raw` (a node.path expression, resolved via resolve_node_path())
    imported as an actual `Chain` subclass — used by `len`/`insert`/
    `push`/`pop`, which operate on the list itself (never an indexed
    item — those take `n` as a plain argument, not `[N]` bracket syntax).
    Raises if there's no such node, or it isn't a Chain."""
    node_path = resolve_node_path(raw)
    node_cls = _import_node(node_path)
    if not issubclass(node_cls, Chain):
        raise TopologyValidationError(f"{node_path!r} is not a Chain")
    return node_cls


def parse_kv_args(pairs: list[str]) -> dict[str, str]:
    context = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        context[key] = value
    return context
