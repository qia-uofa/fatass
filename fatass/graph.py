import re
from pathlib import Path

from .core.transform import discover
from .errors import TopologyValidationError
from .topology_ops.scaffold import _all_node_paths

_NONE_ALIAS = "none_node"
_NONE_LABEL = "None"


def _alias(node_path: str) -> str:
    """A PlantUML-safe identifier for a node's dotted path — aliases are
    how cross-package arrows reference a package regardless of nesting."""
    return "n_" + re.sub(r"\W", "_", node_path)


def _build_tree(node_paths: list[str]) -> dict:
    """Nested dict keyed by path segment, mirroring the inclusion
    relation (directory nesting) — e.g. ["a", "a.b"] -> {"a": {"b": {}}}."""
    tree: dict = {}
    for path in node_paths:
        cursor = tree
        for part in path.split("."):
            cursor = cursor.setdefault(part, {})
    return tree


def _render_tree(tree: dict, prefix: str, lines: list[str]) -> None:
    parent_alias = _alias(prefix) if prefix else "topology"
    names = sorted(tree)

    # Declaring one parent's children inside a single `together` block
    # pins them to the same layout rank, so siblings render at the same
    # level instead of the layout engine staggering them.
    if names:
        lines.append("together {")
        for name in names:
            full_path = f"{prefix}.{name}" if prefix else name
            # Labeled with just the last path segment — the tree edges
            # already convey the full path via nesting, and duplicate
            # labels across distinct aliases are valid PlantUML.
            lines.append(f'  class "{name}" as {_alias(full_path)}')
        lines.append("}")

    for name in names:
        full_path = f"{prefix}.{name}" if prefix else name
        # Dotted arrow from child to parent — ".up." keeps the parent
        # rendered above its child (the default direction would otherwise
        # place the arrow's source above its target, upending the tree).
        lines.append(f"{_alias(full_path)} .up.> {parent_alias}")
        _render_tree(tree[name], full_path, lines)


def _is_unrelated(dep_path: str, owner_path: str) -> bool:
    """True unless one path is an ancestor of the other (or they're the
    same node) — i.e. they're siblings/cousins in the inclusion tree with
    no existing rank ordering between them."""
    return dep_path != owner_path and not (
        owner_path.startswith(dep_path + ".") or dep_path.startswith(owner_path + ".")
    )


def _dep_arrow(transform_name: str, dep_path: str, owner_path: str) -> str:
    """The "build" transform is the one every node is expected to define,
    so its dependency edges are drawn bold to stand out from the rest.

    A dependency edge between tree-unrelated nodes (not one an ancestor of
    the other) gets a "right" direction hint — left as a default top-down
    arrow, it competes with the inclusion tree for vertical rank and can
    drag a same-level sibling out of its `together` block (build isn't
    part of the tree). An edge between an ancestor and its own descendant
    already agrees with the tree's existing vertical order, so it needs
    no hint."""
    style = "[bold]" if transform_name == "build" else ""
    direction = "right" if _is_unrelated(dep_path, owner_path) else ""
    return f"-{style}{direction}->"


def build_graph(root: str | None = None) -> str:
    """A PlantUML diagram of the topology: a class tree (dotted arrows from
    each child to its parent) for the inclusion relation, plus one arrow
    per transform dependency for the dependency relation, labeled with the
    transform's name (unlabeled for "build", since every node has one) and
    pointing from the dependency into the node that depends on it — bold
    for the "build" transform, plain otherwise. A transform declared with
    no Node-typed dependency draws from the special "None" node instead.

    With `root=None` the whole topology is drawn (root class = "topology"),
    as before. With `root` given, only that node and its descendants are
    drawn — the root class is labeled with its full dotted path (it has no
    rendered parent to make that path implicit) — and any transform
    dependency on a node outside that subtree is drawn as a single flat
    class labeled with its own full path (like the "None" node) rather
    than pulling in its ancestry."""
    node_paths = _all_node_paths()

    if root is None:
        subtree_paths = set(node_paths)
    else:
        if root not in node_paths:
            raise TopologyValidationError(f"no node at {root!r}")
        subtree_paths = {
            path for path in node_paths if path == root or path.startswith(root + ".")
        }

    lines = ["@startuml"]
    if root is None:
        lines.append('class "topology" as topology')
        _render_tree(_build_tree(node_paths), "", lines)
    else:
        lines.append(f'class "{root}" as {_alias(root)}')
        descendants = [path[len(root) + 1 :] for path in subtree_paths if path != root]
        _render_tree(_build_tree(descendants), root, lines)

    lines.append("")
    lines.append(f'class "{_NONE_LABEL}" as {_NONE_ALIAS}')

    specs_by_node = {node_path: discover(node_path) for node_path in sorted(subtree_paths)}
    external_paths = sorted(
        {
            dep_cls._topology_path()
            for specs in specs_by_node.values()
            for spec in specs
            for dep_cls in spec.dependencies.values()
            if dep_cls._topology_path() not in subtree_paths
        }
    )
    for dep_path in external_paths:
        lines.append(f'class "{dep_path}" as {_alias(dep_path)}')
    lines.append("")

    for node_path in sorted(subtree_paths):
        owner_alias = _alias(node_path)
        for spec in specs_by_node[node_path]:
            label = "" if spec.name == "build" else f" : {spec.name}"
            if not spec.dependencies:
                arrow = _dep_arrow(spec.name, node_path, node_path)
                lines.append(f"{_NONE_ALIAS} {arrow} {owner_alias}{label}")
                continue
            for dep_cls in spec.dependencies.values():
                dep_path = dep_cls._topology_path()
                dep_alias = _alias(dep_path)
                arrow = _dep_arrow(spec.name, dep_path, node_path)
                lines.append(f"{dep_alias} {arrow} {owner_alias}{label}")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def write_graph(output: Path | None, root: str | None = None) -> Path:
    if output is None:
        output = Path(f"./{root if root is not None else 'topology'}.puml")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_graph(root))
    return output
