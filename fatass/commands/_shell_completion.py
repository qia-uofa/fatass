"""Tab-completion for the `shell` REPL: command names, node paths
(dot-separated, completed segment by segment against the real topology
tree), and the `Node.Path/rel/path` / `Node.Path.transformName` target
grammar (`fatass.resolve.targets`)."""

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from .._internal.naming import pascal_case
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
    each returned as a full replacement for `expr` itself. Every command
    now enforces PascalCase node-path segments (see `cwd.expand`), so
    candidates are converted from the real, on-disk snake_case child
    names to PascalCase before being matched/offered."""
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
        for name in (pascal_case(n) for n in _node_children(base))
        if name.startswith(partial)
    ]


def _complete_asset_path(node_expr: str, rel: str) -> list[str]:
    """Completions for the `rel/path` portion of a `Node.Path/rel/path`
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
    def __init__(
        self, command_names: list[str], group_subcommand_names: dict[str, list[str]] | None = None
    ) -> None:
        self._command_names = command_names
        self._group_subcommand_names = group_subcommand_names or {}

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor
        words = text.split(" ")
        word = words[-1]

        # First word: complete against known top-level names — an
        # ungrouped command's own name, or a group's name (e.g. "chain")
        # for a command nested under it.
        if len(words) == 1:
            for name in self._command_names:
                if name.startswith(word):
                    yield Completion(name, start_position=-len(word))
            return

        # Second word, first word is a known group (e.g. "chain len..."):
        # complete against that group's own nested command names, not the
        # generic node-path-expression fallback below.
        if len(words) == 2 and words[0] in self._group_subcommand_names:
            for name in self._group_subcommand_names[words[0]]:
                if name.startswith(word):
                    yield Completion(name, start_position=-len(word))
            return

        if "/" in word:
            node_expr, _, rel = word.partition("/")
            for candidate in _complete_asset_path(node_expr, rel):
                replacement = f"{node_expr}/{candidate}"
                yield Completion(replacement, start_position=-len(word))
            return

        for candidate in _complete_node_expr(word):
            yield Completion(candidate, start_position=-len(word))
