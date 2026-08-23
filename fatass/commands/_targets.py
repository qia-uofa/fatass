def parse_node_path(path: str) -> tuple[str, str | None]:
    """"."-separated node/transform path, e.g.
    "node1.node2.transforms.synthesize" -> ("node1.node2", "synthesize")."""
    parts = path.split(".")
    if len(parts) >= 2 and parts[-2] == "transforms":
        return ".".join(parts[:-2]), parts[-1]
    return path, None


def parse_at_target(target: str) -> tuple[str, str]:
    """<transform>@<node.path> -> (node_path, transform_name). Requires
    the transform half to be present."""
    if "@" not in target:
        raise ValueError(f"expected <transform>@<node>, got {target!r}")
    transform_name, node_path = target.split("@", 1)
    return node_path, transform_name


def parse_maybe_at_target(target: str) -> tuple[str, str | None]:
    """Same as parse_at_target, but a bare node path (no "@") is valid too
    — used where a target may name either a node or a transform on one."""
    if "@" in target:
        transform_name, node_path = target.split("@", 1)
        return node_path, transform_name
    return target, None


def parse_kv_args(pairs: list[str]) -> dict[str, str]:
    context = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        context[key] = value
    return context
