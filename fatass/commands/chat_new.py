import argparse
import importlib
import sys

from .._internal.naming import pascal_node_path
from ..core.transform import _import_node
from ..errors import FreeError, TopologyValidationError
from ..node.chat import Chat
from ..topology_ops.scaffold import create_node
from ._targets import parse_create_target
from .base import Command


class ChatNewCommand(Command):
    name = "new"
    group = "chat"
    help = "create a Chat node if missing, then start a new claude session in its home dir"
    mutates_topology = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help=(
                "node.path, optionally suffixed with <Chat prompt:str=...> "
                "(same space-separated named-argument grammar `create` "
                "itself uses — quote a value that needs to contain a "
                "space or comma, e.g. prompt:str=\"hi there\") to set this "
                "chat's own seed PROMPT when first creating it — defaults "
                "to <Chat> (base class Chat) even with no suffix given at "
                "all, unlike plain `create`'s own default of <Node>"
            ),
        )

    def run(self, args: argparse.Namespace) -> int:
        created = False
        try:
            node_path, transform_name, base_class, _dep_paths, _plain_params, class_kwargs = (
                parse_create_target(args.target)
            )
            if transform_name is not None:
                raise TopologyValidationError(
                    f"chat new only creates a Chat node, not a transform: {args.target!r}"
                )
            if base_class == "Node":
                # No <NodeSubclass> suffix at all was given — `chat new`'s
                # whole point is to create a Chat, so default to that
                # instead of parse_create_target's own generic <Node>.
                base_class = "Chat"
            elif base_class != "Chat":
                raise TopologyValidationError(
                    f"chat new only creates a Chat node, got <{base_class}> in {args.target!r}"
                )

            created = create_node(node_path, base_class, class_kwargs)
            if created:
                # Unlike plain `create` (which leaves this to cli.main()'s
                # post-command reload + after_reload(), since it only
                # needs on_created() to run eventually), this command
                # needs the freshly-scaffolded node importable and
                # initialized right now, in order to call .start() on it
                # within this same run(). A brand-new module was just
                # written to disk — invalidate_caches() (not the heavier
                # reload_all(), which would evict and reimport the WHOLE
                # topology tree from scratch) is enough: it only clears
                # importlib's own stale directory-listing cache (relevant
                # in a long-running process like the `shell` REPL, where
                # an earlier command may have already listed this node's
                # parent package's contents before this one existed).
                importlib.invalidate_caches()
                _import_node(node_path).on_created()

            node_cls = _import_node(node_path)
            if not issubclass(node_cls, Chat):
                raise TopologyValidationError(
                    f"{pascal_node_path(node_path)} already exists and isn't a Chat"
                )
        except (TopologyValidationError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        display = pascal_node_path(node_path)
        print(f"{display}: {'created, ' if created else ''}starting a new chat session...")
        try:
            result = node_cls.start()
        except FreeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"{display}: chat session closed (exit {result.returncode})")
        return 0
