import re

from ..errors import TopologyValidationError
from ..resolve.cwd import ROOT, expand

_BASE_CLASS_SUFFIX = re.compile(r"\(([A-Za-z_][A-Za-z0-9_]*)\)$")
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


def parse_create_target(target: str) -> tuple[str, str | None, str, list[str]]:
    """Same as parse_maybe_at_target, but also accepts:

    - a trailing "(NodeSubclass)" on the target — e.g. "members(NodeList)"
      or "build@members(NodeList)" — naming the `fatass.<NodeSubclass>`
      base class a newly-created node should subclass instead of the
      default `fatass.Node`. The suffix is only meaningful for creating a
      node, so it's stripped before the rest of the target is parsed.
    - "<transform>(<dep1>,<dep2>,...)@<node.path>" — e.g.
      "build(node1,node2)@node" — naming dependency node.paths to bind
      onto the newly-created transform right after it's scaffolded (the
      deterministic `bind` operation, not an agent call). Mutually
      exclusive with the "(NodeSubclass)" suffix (that one only applies
      to a bare node target, this one only to a "<transform>@..." one).

    Returns (node_path, transform_name, base_class, dep_node_paths) — the
    last always [] except for the "<transform>(deps)@<node>" form. Only
    used by `create` — every other command's targets don't create nodes."""
    deps_match = _TRANSFORM_WITH_DEPS.match(target)
    if deps_match:
        transform_name = deps_match.group("transform")
        dep_paths = [
            resolve_node_path(d.strip())
            for d in deps_match.group("deps").split(",")
            if d.strip()
        ]
        node_path = resolve_node_path(deps_match.group("node"))
        return node_path, transform_name, "Node", dep_paths

    match = _BASE_CLASS_SUFFIX.search(target)
    if match:
        base_class = match.group(1)
        target = target[: match.start()]
    else:
        base_class = "Node"
    node_path, transform_name = parse_maybe_at_target(target)
    return node_path, transform_name, base_class, []


def parse_kv_args(pairs: list[str]) -> dict[str, str]:
    context = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        context[key] = value
    return context
