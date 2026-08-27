"""Tab-completion for the `shell` REPL: command names, node paths
(dot-separated, completed segment by segment against the real topology
tree), and the `node.path/rel/path` / `transform@node.path` target
grammar (`fatass.resolve.targets`)."""

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from ..resolve.cwd import ROOT, expand
from ..topology_ops.scaffold import _assets_dir, _all_node_paths, _node_dir


def _node_children(prefix_path: str) -> list[str]:
    """Immediate child node names (last path segment only) of the node at
    `prefix_path` (ROOT for the topology root itself)."""
    children = set()
    prefix = "" if prefix_path == ROOT else prefix_path + "."
    for path in _all_node_paths():
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        children.add(rest.split(".", 1)[0])
    return sorted(children)


def _complete_node_expr(expr: str) -> list[str]:
    """Completions for a (possibly partial) node-path expression `expr`,
    each returned as a full replacement for `expr` itself."""
    head, _, partial = expr.rpartition(".")
    try:
        # expand("") already resolves to the current node itself (its dot
        # semantics treat an empty leading segment as "stay put"), so a
        # bare partial word (no "." typed yet) completes against the
        # current node's own children, not the topology root's.
        base = expand(head)
    except Exception:
        return []
    prefix = f"{head}." if head else ""
    return [
        prefix + name
        for name in _node_children(base)
        if name.startswith(partial)
    ]


def _complete_asset_path(node_expr: str, rel: str) -> list[str]:
    """Completions for the `rel/path` portion of a `node.path/rel/path`
    target, as full replacements for `rel` itself."""
    try:
        node_path = expand(node_expr)
    except Exception:
        return []
    from ..topology_ops import scaffold

    base = scaffold._HOME_ROOT if node_path == ROOT else _assets_dir(node_path)
    if not base.is_dir():
        return []

    head, _, partial = rel.rpartition("/")
    listing_dir = base / head if head else base
    if not listing_dir.is_dir():
        return []
    prefix = f"{head}/" if head else ""

    out = []
    for entry in sorted(listing_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.startswith(partial):
            continue
        name = entry.name + "/" if entry.is_dir() else entry.name
        out.append(prefix + name)
    return out


class ShellCompleter(Completer):
    def __init__(self, command_names: list[str]) -> None:
        self._command_names = command_names

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor
        words = text.split(" ")
        word = words[-1]

        # First word: complete against known command names.
        if len(words) == 1:
            for name in self._command_names:
                if name.startswith(word):
                    yield Completion(name, start_position=-len(word))
            return

        if "/" in word:
            node_expr, rel = word.split("/", 1)
            for candidate in _complete_asset_path(node_expr, rel):
                replacement = f"{node_expr}/{candidate}"
                yield Completion(replacement, start_position=-len(word))
            return

        node_expr = word.split("@", 1)[-1]
        transform_prefix = word[: len(word) - len(node_expr)]
        for candidate in _complete_node_expr(node_expr):
            replacement = transform_prefix + candidate
            yield Completion(replacement, start_position=-len(word))
