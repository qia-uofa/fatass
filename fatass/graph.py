import re
from pathlib import Path

from .scaffold import _all_node_paths
from .transform import discover

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


def _render_tree(tree: dict, prefix: str, indent: str, lines: list[str]) -> None:
    for name in sorted(tree):
        full_path = f"{prefix}.{name}" if prefix else name
        lines.append(f'{indent}package "{full_path}" as {_alias(full_path)} {{')
        _render_tree(tree[name], full_path, indent + "  ", lines)
        lines.append(f"{indent}}}")


def build_graph() -> str:
    """A PlantUML diagram of the whole topology: a package tree for the
    inclusion relation (root = topology), plus one arrow per transform
    dependency for the dependency relation, labeled with the transform's
    name and pointing from the dependency into the node that depends on
    it. A transform declared with no Node-typed dependency (not possible
    via transform.discover() today, but handled for robustness) draws
    from the special "None" node instead."""
    node_paths = _all_node_paths()

    lines = ["@startuml", 'package "topology" as topology {']
    _render_tree(_build_tree(node_paths), "", "  ", lines)
    lines.append("}")
    lines.append("")
    lines.append(f'class "{_NONE_LABEL}" as {_NONE_ALIAS}')
    lines.append("")

    for node_path in sorted(node_paths):
        owner_alias = _alias(node_path)
        for spec in discover(node_path):
            if not spec.dependencies:
                lines.append(f"{_NONE_ALIAS} --> {owner_alias} : {spec.name}")
                continue
            for dep_cls in spec.dependencies.values():
                dep_alias = _alias(dep_cls._topology_path())
                lines.append(f"{dep_alias} --> {owner_alias} : {spec.name}")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def write_graph(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_graph())
    return output
