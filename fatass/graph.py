import re
from pathlib import Path

from .core.transform import discover, _import_node
from .errors import TopologyValidationError
from .topology_ops.scaffold import _all_node_paths

_NONE_ALIAS = "none_node"
_NONE_LABEL = "None"


def _alias(node_path: str) -> str:
    """A PlantUML-safe identifier for a node's dotted path — aliases are
    how cross-package arrows reference a package regardless of nesting."""
    return "n_" + re.sub(r"\W", "_", node_path)


def _transform_signature(spec) -> str:
    """"<name>(<dep1>,<dep2>,<plain>:<type>=<default>,...)" — the same
    shape as the `create <transform>(<deps>)@<node>` target syntax that
    would declare this transform in the first place: Node-typed
    dependencies listed by their parameter name (deps first), then plain
    context parameters as their own real "name: type = default" text
    (`str(inspect.Parameter)` already renders exactly that)."""
    parts = list(spec.dependencies.keys()) + [str(p) for p in spec.context_params.values()]
    return f"{spec.name}({', '.join(parts)})"


def _discover_cached(node_path: str, cache: dict[str, list]) -> list:
    if node_path not in cache:
        try:
            cache[node_path] = discover(node_path)
        except Exception:
            cache[node_path] = []
    return cache[node_path]


def _class_block(node_path: str, alias: str, specs_cache: dict[str, list], indent: str = "") -> list[str]:
    """A full PlantUML class declaration for `node_path`: header is just
    the node's own real Python class name (falling back to the bare
    node_path if the class can't be imported) — NOT combined with its
    repr in the class name itself: PlantUML treats a "<...>" inside a
    quoted class name as a generic-type stereotype badge, not literal
    text, which renders as a stray floating tag rather than the intended
    label. The repr is instead the body's own first member line, followed
    by each defined transform's signature (alphabetical by name) — the
    transform equivalent of a UML class's methods, letting a dependency
    arrow target a specific transform (`alias::name`) instead of the
    class as a whole."""
    try:
        node_cls = _import_node(node_path)
        header = node_cls.__name__
        kind_line = f"<{node_cls!r}>"
    except Exception:
        header = node_path
        kind_line = None

    specs = sorted(_discover_cached(node_path, specs_cache), key=lambda s: s.name)
    if kind_line is None and not specs:
        return [f'{indent}class "{header}" as {alias}']

    lines = [f'{indent}class "{header}" as {alias} {{']
    if kind_line is not None:
        lines.append(f"{indent}  {kind_line}")
        if specs:
            # A "--" separator bar between the kind line and the actual
            # transform members — two different sorts of entry (node
            # metadata vs. methods), so visually grouped apart rather
            # than run together as one undifferentiated list.
            lines.append(f"{indent}  --")
    for spec in specs:
        lines.append(f"{indent}  {_transform_signature(spec)}")
    lines.append(f"{indent}}}")
    return lines


def _build_tree(node_paths: list[str]) -> dict:
    """Nested dict keyed by path segment, mirroring the inclusion
    relation (directory nesting) — e.g. ["a", "a.b"] -> {"a": {"b": {}}}."""
    tree: dict = {}
    for path in node_paths:
        cursor = tree
        for part in path.split("."):
            cursor = cursor.setdefault(part, {})
    return tree


def _render_tree(tree: dict, prefix: str, lines: list[str], specs_cache: dict[str, list]) -> None:
    parent_alias = _alias(prefix) if prefix else "topology"
    names = sorted(tree)

    # Declaring one parent's children inside a single `together` block
    # pins them to the same layout rank, so siblings render at the same
    # level instead of the layout engine staggering them.
    if names:
        lines.append("together {")
        for name in names:
            full_path = f"{prefix}.{name}" if prefix else name
            lines.extend(_class_block(full_path, _alias(full_path), specs_cache, indent="  "))
        lines.append("}")

    for name in names:
        full_path = f"{prefix}.{name}" if prefix else name
        # Dotted arrow from child to parent — ".up." keeps the parent
        # rendered above its child (the default direction would otherwise
        # place the arrow's source above its target, upending the tree).
        lines.append(f"{_alias(full_path)} .up.> {parent_alias}")
        _render_tree(tree[name], full_path, lines, specs_cache)


def _dep_arrow(transform_name: str, *, self_loop: bool) -> str:
    """The "build" transform is the one every node is expected to define,
    so its dependency edges are drawn bold to stand out from the rest.

    A cross-class edge always gets an explicit "right" direction hint —
    never left as a default top-down arrow — so it connects side-to-side
    (left/right edge of one box to left/right edge of the other) rather
    than competing with the inclusion tree's own vertical (".up.>") edges
    for top/bottom rank and connection points. A self-loop is the one
    exception: forcing "right" on an edge whose two ends are the SAME
    box makes PlantUML route it as a large arc swinging out and back —
    with several self-loops on neighboring classes, those arcs cross
    right over each other and any box in between. Left with no direction
    hint, PlantUML draws a small loop directly on the box instead."""
    style = "[bold]" if transform_name == "build" else ""
    direction = "" if self_loop else "right"
    return f"-{style}{direction}->"


def build_graph(root: str | None = None) -> str:
    """A PlantUML diagram of the topology: a class tree (dotted arrows from
    each child to its parent) for the inclusion relation, each class
    listing its own transforms' signatures as members, plus one unlabeled
    arrow per transform dependency for the dependency relation — pointing
    from the dependency's class (never from the transform) to the specific
    depending transform (`owner::transform_name`, never just the owning
    class) — bold for the "build" transform, plain otherwise. A transform
    declared with no Node-typed dependency draws from the special "None"
    node instead; a transform depending on its own node draws a self-loop
    from the class name back to that same transform member.

    With `root=None` the whole topology is drawn (root class = "topology"),
    as before. With `root` given, only that node and its descendants are
    drawn — the root class has no rendered parent, so it's labeled with
    its own class/repr like any other node — and any transform dependency
    on a node outside that subtree is drawn as its own flat class (like
    the "None" node) rather than pulling in its ancestry."""
    node_paths = _all_node_paths()

    if root is None:
        subtree_paths = set(node_paths)
    else:
        if root not in node_paths:
            raise TopologyValidationError(f"no node at {root!r}")
        subtree_paths = {
            path for path in node_paths if path == root or path.startswith(root + ".")
        }

    specs_cache: dict[str, list] = {}

    lines = ["@startuml"]
    if root is None:
        lines.append('class "topology" as topology')
        _render_tree(_build_tree(node_paths), "", lines, specs_cache)
    else:
        lines.extend(_class_block(root, _alias(root), specs_cache))
        descendants = [path[len(root) + 1 :] for path in subtree_paths if path != root]
        _render_tree(_build_tree(descendants), root, lines, specs_cache)

    lines.append("")
    lines.append(f'class "{_NONE_LABEL}" as {_NONE_ALIAS}')

    external_paths = sorted(
        {
            dep_cls._topology_path()
            for node_path in subtree_paths
            for spec in _discover_cached(node_path, specs_cache)
            for dep_cls in spec.dependencies.values()
            if dep_cls._topology_path() not in subtree_paths
        }
    )
    for dep_path in external_paths:
        lines.extend(_class_block(dep_path, _alias(dep_path), specs_cache))
    lines.append("")

    for node_path in sorted(subtree_paths):
        owner_alias = _alias(node_path)
        self_dep_names: list[str] = []
        for spec in sorted(_discover_cached(node_path, specs_cache), key=lambda s: s.name):
            target = f"{owner_alias}::{spec.name}"
            if not spec.dependencies:
                arrow = _dep_arrow(spec.name, self_loop=False)
                lines.append(f"{_NONE_ALIAS} {arrow} {target}")
                continue
            for dep_cls in spec.dependencies.values():
                dep_path = dep_cls._topology_path()
                if dep_path == node_path:
                    # A self-dependency edge aimed at one specific member
                    # (like a cross-class edge is) forces PlantUML to
                    # route the loop all the way into that particular
                    # row — with several self-bound transforms on one
                    # node (common with the "f@node" self-bind
                    # convention), that's several separately-routed arcs
                    # converging on the same box, which knot together
                    # into a tangled mess rather than reading as several
                    # distinct relationships. The member list already
                    # names every transform, so the loop itself only
                    # needs to say "this node depends on itself" once —
                    # collected here, emitted as one loop after the fact.
                    self_dep_names.append(spec.name)
                    continue
                dep_alias = _alias(dep_path)
                arrow = _dep_arrow(spec.name, self_loop=False)
                lines.append(f"{dep_alias} {arrow} {target}")
        if self_dep_names:
            bold_name = "build" if "build" in self_dep_names else ""
            arrow = _dep_arrow(bold_name, self_loop=True)
            lines.append(f"{owner_alias} {arrow} {owner_alias}")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def write_graph(output: Path | None, root: str | None = None) -> Path:
    if output is None:
        output = Path(f"./{root if root is not None else 'topology'}.puml")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_graph(root), encoding="utf-8")
    return output
