import argparse
import sys

from ..node.node import Node
from ..node import chain as _chain  # noqa: F401 -- registers Chain as a Node subclass
from ..node.dictionary import Dictionary
from ..node import single as _single  # noqa: F401 -- registers Single & co. as Node subclasses
from ..node import array as _array  # noqa: F401 -- registers Array & co. as Node subclasses
from ..node import repo as _repo  # noqa: F401 -- registers Repo as a Node subclass
from ..node import dir as _dir  # noqa: F401 -- registers Dir as a Node subclass
from ..node import chat as _chat  # noqa: F401 -- registers Chat as a Node subclass
from .._internal.naming import pascal_node_path
from ..errors import TopologyValidationError
from ..topology_ops.bind import add_plain_params, bind_transform
from ..topology_ops.scaffold import _node_dir, create_node, create_transform
from ._targets import parse_create_target
from .base import Command


def _framework_node_classes(cls: type[Node]) -> dict[str, type[Node]]:
    """Every `fatass.node.*`-defined `Node` subclass (Single/Array/Chain and
    all their typed variants), keyed by class name -- walked recursively off
    `Node` itself so a new subclass (e.g. a new `SingleCsv`) is picked up
    automatically without a matching entry here. Restricted to classes
    defined in `fatass.node.*` so an actual topology node (e.g. a user's own
    `Papers(Chain)`) never counts as a valid `<NodeSubclass>` target."""
    result: dict[str, type[Node]] = {}
    for sub in cls.__subclasses__():
        if sub.__module__.startswith("fatass.node."):
            result[sub.__name__] = sub
        result.update(_framework_node_classes(sub))
    return result


_BASE_CLASSES: dict[str, type[Node]] = {"Node": Node, **_framework_node_classes(Node)}
_BASE_CLASSES["Dict"] = Dictionary
"""`<Dict>` is accepted as a shorter alias for `<Dictionary>` (matching
`fatass dict`'s own group name) -- purely an input-side convenience:
`_base_kind().__name__` (and so every rendered signature) still always
shows the real class name, "Dictionary"; only `create`/`touch`'s own
`<NodeType>` parsing accepts the alias, not any output."""


class CreateCommand(Command):
    name = "create"
    help = "scaffold a node or transform if it doesn't exist yet"
    mutates_topology = True

    def __init__(self) -> None:
        self._created_node_path: str | None = None

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help=(
                "node.path, or PathedNodeSignature.transformName to create "
                "a transform — a node.path where every segment is "
                "PascalCase (matching that node's own class name, e.g. "
                "\"Jrpg.Design.Overview\"), then the transform's own "
                "lowerCamelCase name, e.g. \"Jrpg.Design.Overview.build\"; "
                "optionally followed by \"<params>\" (space-separated "
                "name:type=value entries, e.g. \"build<n:int=5>\") and/or "
                "\"(deps)\" (comma-separated PathedNodeSignature "
                "dependencies, bound the same way as `bind`, e.g. "
                "\"build(Jrpg.Design.BrainStorm)\") — either bracket is "
                "independently omittable and defaults to empty "
                "(\"Node.transform<params>\" alone means "
                "\"Node.transform<params>()\"; bare \"Node.transform\" "
                "means no params and no deps at all); a dependency may "
                "itself carry a trailing \"<NodeType(args)>\" assertion, "
                "and a plain parameter's type may add \"=default\" for a "
                "default value, e.g. \"n:int=0\" — a str default is re-"
                "quoted by fatass itself, so it survives the shell's own "
                "quote-stripping; a node.path (for the plain node-"
                "creation form) may end with <NodeSubclass> (e.g. "
                "\"members<Chain>\") to subclass fatass.<NodeSubclass> "
                "instead of fatass.Node, optionally followed by its own "
                "space-separated args — bare field names and/or (for an "
                "Array) \"dim=<int>x<int>x...\" (e.g. \"grid<ArrayCsv "
                "field1 field2 dim=2x2x2>\"), and/or, for a named/typed "
                "class attribute (e.g. Chat's PROMPT), \"name:type=value\" "
                "entries (e.g. \"my_chat<Chat prompt:str=hi>\") — one "
                "grammar for every kind of arg, the same shape a node's "
                "own displayed signature (see `fatass ls`) already uses; "
                "quote a value that needs to contain a space or comma, "
                "e.g. prompt:str=\"hi there\""
            ),
        )

    def run(self, args: argparse.Namespace) -> int:
        self._created_node_path = None
        bound: list[str] = []
        added_params: list[str] = []
        try:
            node_path, transform_name, base_class, dep_paths, plain_params, class_kwargs = (
                parse_create_target(args.target)
            )
            if base_class not in _BASE_CLASSES:
                raise ValueError(
                    f"unknown NodeSubclass {base_class!r} "
                    f"(expected one of {sorted(_BASE_CLASSES)})"
                )
            # `base_class` may be an alias (e.g. "Dict") — the generated
            # file's own `class X(fatass.<name>):` line needs the REAL
            # class name (`fatass.Dict` isn't a real attribute, only
            # `fatass.Dictionary` is), so resolve it once, right here,
            # before it's used for anything else below.
            base_class = _BASE_CLASSES[base_class].__name__
            if transform_name is not None:
                if base_class != "Node":
                    raise ValueError(
                        f"<NodeSubclass> only applies to creating a node, not a "
                        f"transform: {args.target!r}"
                    )
                created = create_transform(node_path, transform_name)
                label = f"{pascal_node_path(node_path)}.transforms.{transform_name}"
                if created:
                    try:
                        if dep_paths:
                            bound = bind_transform(node_path, transform_name, dep_paths)
                        if plain_params:
                            added_params = add_plain_params(
                                node_path, transform_name, plain_params
                            )
                    except BaseException:
                        # This call is the one that created the stub —
                        # a failure wiring deps/params onto it must not
                        # leave a half-made transform file behind; undo
                        # the create_transform() step too so the whole
                        # command is all-or-nothing.
                        transform_file = _node_dir(node_path) / f"{transform_name}.py"
                        if transform_file.is_file():
                            transform_file.unlink()
                        raise
            else:
                created = create_node(node_path, base_class, class_kwargs)
                label = pascal_node_path(node_path)
                if created:
                    self._created_node_path = node_path
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{label}: already exists" if not created else f"{label}: created")
        if bound:
            print(f"{label}: bound {', '.join(pascal_node_path(p) for p in bound)}")
        if added_params:
            print(f"{label}: added parameters {', '.join(added_params)}")
        return 0

    def after_reload(self, args: argparse.Namespace) -> None:
        """Called by cli.main() once fatass.topology has been reloaded
        post-command — only then is a just-scaffolded node's class
        actually importable, so `on_created()` (e.g. Single/Array
        materializing their fixed-name file(s)) has to run here rather
        than inline in run()."""
        if self._created_node_path is None:
            return
        # Local import: avoids importing core.transform (which imports
        # topology_ops.scaffold, which imports this module's own
        # topology_ops.bind sibling) at module load time.
        from ..core.transform import _import_node

        node_cls = _import_node(self._created_node_path)
        node_cls.on_created()
