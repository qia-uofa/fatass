from ..errors import TopologyValidationError
from ..resolve.cwd import ROOT, expand


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


def parse_kv_args(pairs: list[str]) -> dict[str, str]:
    context = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        context[key] = value
    return context
