import argparse
import sys

from ..core.transform import apply_transform
from ..errors import TopologyValidationError
from ..topology_ops.scaffold import _node_dir
from ._targets import parse_kv_args, resolve_chain
from .base import Command


class PushCommand(Command):
    name = "push"
    help = (
        "if the Chain has its own `push` transform, apply it (shorthand for "
        "`apply push@<node.path>`); otherwise append one item, seeded as a "
        "copy of the dummy head's own content"
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("node_path", help="node.path of a Chain")
        parser.add_argument(
            "args",
            nargs="*",
            help="key=value context arguments for the Chain's own `push` transform, if it has one",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            list_cls = resolve_chain(args.node_path)
            node_path = list_cls._topology_path()
            own_file_stem = node_path.rsplit(".", 1)[-1]
            has_push_transform = own_file_stem != "push" and (
                _node_dir(node_path) / "push.py"
            ).is_file()

            if has_push_transform:
                context = parse_kv_args(args.args)
                apply_transform(node_path, "push", context)
                print(f"{node_path}.transforms.push: applied")
                return 0

            if args.args:
                raise TopologyValidationError(
                    f"{node_path!r} has no push transform of its own — "
                    f"extra arguments {args.args} only apply to one"
                )
            index = list_cls.length()
            list_cls.insert(index)
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{node_path}: pushed item {index}")
        return 0
