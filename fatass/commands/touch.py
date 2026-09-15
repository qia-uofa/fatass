import argparse
import importlib
import sys
from pathlib import Path
from typing import Callable

from .._internal.naming import pascal_node_path, snake_case
from ..core.transform import _import_node
from ..errors import TopologyValidationError
from ..signature import (
    _split_top_level_commas,
    _split_top_level_semicolons,
    _split_trailing_curly,
    _split_trailing_parens,
    _split_type_suffix,
)
from ._targets import (
    _looks_like_transform_target,
    parse_bare_transform_spec,
    parse_pathed_transform_target,
    resolve_node_path,
)
from .base import Command


def _strip_comments(raw: str) -> str:
    """Drop a "#" and everything after it through end-of-line, for every
    unquoted "#" in `raw` — lets a multi-statement touch input (see
    `_split_top_level_statements`), especially one that mixes a large
    node-tree signature with a long list of transform-creation targets,
    carry the same kind of section-header commentary a hand-written
    shell script would. A "#" inside a "..."-quoted value (e.g. a `Chat`
    prompt that happens to mention one) is left alone — this only ever
    strips a "#" that isn't already inside quotes."""
    out: list[str] = []
    in_quotes = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if in_quotes:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(raw[i + 1])
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            nl = raw.find("\n", i)
            i = n if nl == -1 else nl
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _peek_trailing_comment(raw: str, i: int, n: int, seps: str) -> tuple[str | None, int]:
    """From `raw[i]`, skip any run of characters in `seps`, then — if a
    "#" follows before any newline — return its stripped text and the
    index just past its own line; otherwise `(None, i)` (nothing
    consumed). Shared by `_extract_transform_comments`'s two "trailing
    same-line comment" checks (a bare "{...}"-block entry's own ";", and
    a standalone top-level transform statement's own end)."""
    j = i
    while j < n and raw[j] in seps:
        j += 1
    if j < n and raw[j] == "#":
        nl = raw.find("\n", j)
        text = raw[j + 1 : nl if nl != -1 else n].strip()
        return text, (n if nl == -1 else nl + 1)
    return None, i


def _extract_transform_comments(raw: str) -> list[str | None]:
    """Walks `raw` — touch's ORIGINAL, un-comment-stripped target text —
    once, left to right, and returns one comment-or-None per transform
    occurrence, in the exact same order `TouchCommand.run`'s own two-pass
    scan discovers them in (see `_split_top_level_statements`/
    `_parse_touch_spec`/`_touch`'s own recursion) — used by `touch -m` to
    pair each transform with its own modify prompt, if it has one.
    Because the grammar's own bracket nesting is already strictly
    left-to-right/pre-order (a node's own "{...}" always textually
    precedes its "(...)" children, exactly the order `_touch`'s own
    recursion populates `_pending_transforms` in), one linear scan
    naturally produces occurrences in the right final order without
    needing to mirror that recursion here.

    A transform occurrence is either a bare "name<params>(deps);" entry
    inside some node's "{...}" block, or a standalone top-level
    "PathedNodeSignature.transformName<params>(deps)" statement — decided
    the same way `_looks_like_transform_target` does, against the same
    comment-stripped text `TouchCommand.run` itself parses (comments
    never contribute to that text here either).

    A comment attaches to a transform in one of two positions (see
    `TouchCommand.add_arguments`'s own "-m" help text):
    1. one or more comment-only lines immediately before it (multi-line
       allowed), with no blank line breaking the run;
    2. a single trailing "#..." comment on the very same line right
       after its own closing ";" (a bare entry) or its own end (a
       standalone statement) — only when that transform's own statement
       is itself all on one line (no newline of its own)."""
    comments: list[str | None] = []

    depth = 0
    in_quotes = False
    just_saw_newline = True

    top_buf: list[str] = []
    top_started = False
    top_has_newline = False
    top_leading: list[str] = []

    bare_started = False
    bare_has_newline = False
    bare_leading: list[str] = []

    n = len(raw)

    def finalize_top(trailing_from: int | None) -> int | None:
        nonlocal top_buf, top_started, top_has_newline, top_leading
        entry_text = "".join(top_buf)
        result_i = None
        if _looks_like_transform_target(entry_text):
            comment = None
            if trailing_from is not None and not top_has_newline:
                trailing, new_i = _peek_trailing_comment(raw, trailing_from, n, " \t,")
                if trailing is not None:
                    comment = trailing
                    result_i = new_i
            if comment is None:
                comment = "\n".join(top_leading) if top_leading else None
            comments.append(comment)
        top_buf = []
        top_started = False
        top_has_newline = False
        top_leading = []
        return result_i

    i = 0
    while i < n:
        ch = raw[i]

        if in_quotes:
            top_buf.append(ch)
            just_saw_newline = False
            if ch == "\\" and i + 1 < n:
                top_buf.append(raw[i + 1])
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue

        if ch == '"':
            in_quotes = True
            top_buf.append(ch)
            top_started = True
            bare_started = True
            just_saw_newline = False
            i += 1
            continue

        if ch == "#":
            nl = raw.find("\n", i)
            text = raw[i + 1 : nl if nl != -1 else n].strip()
            if not top_started:
                top_leading.append(text)
            if depth > 0 and not bare_started:
                bare_leading.append(text)
            i = n if nl == -1 else nl + 1
            just_saw_newline = nl != -1
            continue

        if ch == ";" and depth > 0:
            trailing, new_i = _peek_trailing_comment(raw, i + 1, n, " \t")
            if trailing is not None and not bare_has_newline:
                comment = trailing
                i = new_i
            else:
                comment = "\n".join(bare_leading) if bare_leading else None
                i += 1
            comments.append(comment)
            bare_started = False
            bare_has_newline = False
            bare_leading = []
            just_saw_newline = False
            continue

        if ch in "(<{":
            depth += 1
            top_buf.append(ch)
            top_started = True
            if ch == "{":
                bare_started = False
                bare_has_newline = False
                bare_leading = []
            else:
                bare_started = True
            just_saw_newline = False
            i += 1
            continue

        if ch in ")>}":
            depth -= 1
            top_buf.append(ch)
            bare_started = True
            just_saw_newline = False
            i += 1
            continue

        if ch == "\n":
            if just_saw_newline:
                top_leading = []
                bare_leading = []
            just_saw_newline = True
            if top_started:
                top_has_newline = True
            if bare_started:
                bare_has_newline = True
            if depth == 0 and top_started:
                new_i = finalize_top(i)
                i = new_i if new_i is not None else i + 1
            else:
                i += 1
            continue

        if ch in " \t":
            if depth == 0 and top_started:
                new_i = finalize_top(i)
                i = new_i if new_i is not None else i + 1
            else:
                i += 1
            continue

        if ch == "," and depth == 0:
            just_saw_newline = False
            if top_started:
                new_i = finalize_top(i)
                i = new_i if new_i is not None else i + 1
            else:
                i += 1
            continue

        top_buf.append(ch)
        top_started = True
        bare_started = True
        just_saw_newline = False
        i += 1

    if top_started:
        finalize_top(None)

    return comments


def _split_children_block(raw: str) -> tuple[str, str | None]:
    """`touch`'s own name for `fatass.signature._split_trailing_parens`
    — a node-tree entry's trailing "(Child1<Type1>(...),Child2<Type2>)"
    children block IS just a trailing "(...)" group, the exact same
    shape (and same ambiguity to resolve — see that function's own
    docstring) the transform-target grammar's "(deps)" group peels off
    with, so the algorithm lives there, shared, rather than duplicated
    here."""
    return _split_trailing_parens(raw)


def _split_transforms_block(raw: str) -> tuple[str, str | None]:
    """`touch`'s own name for `fatass.signature._split_trailing_curly` —
    a node-tree entry's own optional "{transform1<params>(deps);...}"
    transforms block (see `fatass.signature.FULL_SIGNATURE`), peeled
    from what's left AFTER `_split_children_block` has already removed
    any trailing "(...)" children block (the two sit in that order —
    "{...}(...)" — see `_parse_touch_spec`)."""
    return _split_trailing_curly(raw)


def _split_top_level_statements(raw: str) -> list[str]:
    """Split `raw` — touch's whole input, one or more node-tree
    signatures and/or `<transform>@<node.path>` transform-creation
    targets — into one top-level statement per entry, to be processed
    independently and in order (see `TouchCommand.run`). Statements need
    no explicit separator of their own: any run of whitespace and/or
    commas, while bracket depth (`<...>`/`(...)`/`{...}`, and any
    "..."-quoted region) is back at 0, ends one statement and begins the
    next — so a file may freely mix one big node-tree signature (with
    its own multi-line, semicolon-terminated "{...}" transforms block)
    with any number of transform-creation lines after it (one per line,
    blank lines allowed, with or without trailing commas)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_quotes = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if in_quotes:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(raw[i + 1])
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            buf.append(ch)
        elif ch in "(<{":
            depth += 1
            buf.append(ch)
        elif ch in ")>}":
            depth -= 1
            buf.append(ch)
        elif depth == 0 and (ch.isspace() or ch == ","):
            if buf:
                parts.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_touch_spec(raw: str) -> tuple[str, str | None, dict, list[str], list[str]]:
    """One node's whole touch spec — the top-level target, or one child
    entry inside a "(...)" block — split into (name_or_path, type_name,
    class_kwargs, child_specs, transform_specs). `name_or_path` is the
    top-level target's full PascalCase node.path (converted to real
    snake_case automatically by `resolve_node_path`/
    `fatass.resolve.cwd.expand`, same as any other node.path), or (for a
    child entry) just its own bare class name (e.g. "Topics") —
    `_split_type_suffix` doesn't care which, it only ever looks at the
    trailing "<...>" suffix. `child_specs` is the "(...)" block's own
    content, split into one raw string per child (still unparsed — each
    is parsed the same way, recursively, by the caller) — empty if there
    was no "(...)" block at all. `transform_specs` is the "{...}" block's
    own content (see `fatass.signature.FULL_SIGNATURE`), split into one
    bare "transformName<params>(deps)" string per entry (no node-path
    prefix — the node is this same spec's own `name_or_path`) — empty if
    there was no "{...}" block at all.

    The two blocks are peeled off in the order they actually appear —
    "{...}" before "(...)" textually, but `(...)` is the trailing group
    so it's the first one peeled — see `_split_children_block`/
    `_split_transforms_block`."""
    prefix, block = _split_children_block(raw)
    prefix, transforms_block = _split_transforms_block(prefix)
    stripped, type_name, class_kwargs = _split_type_suffix(prefix)
    child_specs = _split_top_level_commas(block) if block is not None else []
    transform_specs = _split_top_level_semicolons(transforms_block) if transforms_block is not None else []
    return stripped, type_name, class_kwargs, child_specs, transform_specs


class TouchCommand(Command):
    name = "touch"
    help = (
        "scaffold one or more nodes (and recursively their declared "
        "subnodes) and/or transforms from a signature string — a "
        "subnode already declared some other way (e.g. as a real schema "
        "child under a Chain) is left untouched"
    )
    mutates_topology = True

    def __init__(self) -> None:
        self._touched: list[str] = []
        self._modified: list[str] = []
        self._pending_transforms: list[Callable[[], tuple[str, str] | None]] = []

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "target",
            nargs="?",
            default=None,
            help=(
                "one or more statements, processed independently and in "
                "order (so a later one may reference a node an earlier "
                "one just created) — no separator needed between them "
                "beyond whitespace and/or a comma. Each statement is "
                "either a PascalCase node.path (every real name segment "
                "capitalized, matching a node's own class name — "
                "converted back to snake_case the same way a child's own "
                "is, below), optionally suffixed with "
                "<NodeType arg1 arg2> or <NodeType name:type=value ...> "
                "(same grammar `create` itself uses) to give it a "
                "specific type, itself optionally followed by "
                "\"{transform1<params>(deps);transform2<params>(deps);}\" "
                "naming its own transforms (each bare — no node-path "
                "prefix, this node is already known) and/or "
                "\"(Child1<Type1>(...),Child2<Type2>)\" naming its own "
                "direct subnodes (each recursively the same shape) — the "
                "\"{...}\" transforms block comes before \"(...)\", the "
                "exact shape a node's own recursive `FULL_SIGNATURE` (see "
                "`fatass ls -r`) already renders, so copying one "
                "straight into `touch` scaffolds the whole tree — "
                "transforms included — it describes in one shot; a "
                "child's own node.path is its parent's own path plus its "
                "class name converted back to snake_case (e.g. \"Topics\" "
                "-> \".topics\"), and a dep inside \"(...)\" navigates "
                "relative to the transform's own node's PARENT, same as "
                "everywhere else — or a top-level "
                "PathedNodeSignature.transformName<params>(deps) "
                "transform-creation target, same grammar and actions as "
                "`fatass create`'s own (see `fatass create --help`). "
                "Every node (from every statement, including nested "
                "subnodes) is created before any transform is (see "
                "`{...}`/top-level transform targets both), so a "
                "dependency may reference a node declared anywhere else "
                "in this same call, in any order. May freely span "
                "multiple lines (e.g. one indented per nesting level, or "
                "one statement per line) for readability, and a \"#\" "
                "starts a comment running to end of line (unless inside "
                "a quoted value). Each node/transform not already "
                "present is created (existing ones are left alone, "
                "subnodes included). Omit if giving -p/--path instead"
            ),
        )
        parser.add_argument(
            "-p",
            "--path",
            default=None,
            help="read the target signature from this real filesystem "
            "file instead of giving it directly as the target argument "
            "— e.g. one saved from a node's own `fatass ls -r` output",
        )
        parser.add_argument(
            "-m",
            "--modify",
            action="store_true",
            help=(
                "after creating every node and transform, silently `modify` "
                "each newly-created transform that has an associated "
                '"#" comment in the ORIGINAL target text, using that '
                "comment as the modify prompt (transforms that already "
                "existed, or that have no comment, are left alone). A "
                "comment attaches to a transform in one of two positions: "
                "one or more comment-only lines immediately before it "
                "with no blank line in between (multi-line allowed), or "
                "a single trailing \"#...\" comment on the same line "
                "right after its own closing \";\" (a \"{...}\"-block "
                "entry) or its own end (a standalone transform-creation "
                "target) — only when that transform's own statement is "
                "itself all on one line"
            ),
        )

    def _touch(
        self,
        node_path: str,
        type_name: str | None,
        class_kwargs: dict,
        child_specs: list[str],
        transform_specs: list[str],
    ) -> None:
        # Local imports: avoid a commands/-package-load-time cycle
        # through create.py (which itself imports plenty), and matching
        # CreateCommand's own validation of `base_class` — without it, a
        # typo'd/unknown <NodeType> would only surface much later, as a
        # raw AttributeError out of on_created()'s own import below
        # (`fatass.NotARealKind` doesn't exist), by which point the
        # broken file is already sitting on disk, poisoning every other
        # command's own eager `import fatass` until removed by hand.
        from ..topology_ops.scaffold import create_node
        from .create import _BASE_CLASSES

        base_class = type_name if type_name is not None else "Node"
        if base_class not in _BASE_CLASSES:
            raise TopologyValidationError(
                f"{pascal_node_path(node_path)}: unknown <{base_class}> "
                f"(expected one of {sorted(_BASE_CLASSES)})"
            )
        # `base_class` may be an alias (e.g. "Dict") — see create.py's
        # own matching comment for why this has to resolve to the real
        # class name before create_node() ever sees it.
        base_class = _BASE_CLASSES[base_class].__name__
        created = create_node(node_path, base_class, class_kwargs)
        if created:
            # Needs the freshly-scaffolded node importable and its
            # on_created() run right now — a child touched next may
            # itself depend on this node's directory already existing,
            # and a Single/Array/Tuple/etc. node's own managed file(s)
            # should materialize immediately, same expectation as a
            # plain `fatass create` (just done inline here, since this
            # command creates a whole tree in one call rather than one
            # node per invocation — see `chat_new.py` for the same
            # pattern and its own reasoning).
            importlib.invalidate_caches()
            _import_node(node_path).on_created()
            self._touched.append(pascal_node_path(node_path))

        # Deferred, not created here — see `run()`'s own second pass.
        # `node_path` is captured now (this node's own real, already-
        # resolved path); the entry itself is still raw, unparsed text.
        for spec in transform_specs:
            self._pending_transforms.append(lambda np=node_path, s=spec: self._create_bare_transform_entry(np, s))

        for child_spec in child_specs:
            child_name, child_type, child_kwargs, grandchild_specs, grandchild_transform_specs = (
                _parse_touch_spec(child_spec)
            )
            child_path = f"{node_path}.{snake_case(child_name)}"
            self._touch(child_path, child_type, child_kwargs, grandchild_specs, grandchild_transform_specs)

    def _create_transform(
        self, node_path: str, transform_name: str, dep_paths: list[str], plain_params: list[tuple[str, str]]
    ) -> tuple[str, str] | None:
        """Shared by `_create_transform_entry` (the standalone
        `PathedNodeSignature.transformName<params>(deps)` top-level
        statement grammar) and `_create_bare_transform_entry` (a node's
        own "{...}" transforms-block entry) — both already know
        `node_path`/`transform_name`/`dep_paths`/`plain_params`, just
        parsed differently; from here on the actual creation is
        identical, and matches `fatass create`'s own transform-creation
        branch (`CreateCommand.run`) so the three can never drift apart
        on what such a target means or does. Doesn't call free() — same
        as `create`, and same as `_touch`'s own node-creation side."""
        # Local imports: same load-order reasoning as `_touch`'s own.
        from ..topology_ops.bind import add_plain_params, bind_transform
        from ..topology_ops.scaffold import _node_dir, create_transform

        created = create_transform(node_path, transform_name)
        if not created:
            return None
        try:
            if dep_paths:
                bind_transform(node_path, transform_name, dep_paths)
            if plain_params:
                add_plain_params(node_path, transform_name, plain_params)
        except BaseException:
            # Mirrors `CreateCommand.run`'s own all-or-nothing rollback:
            # this call is the one that created the stub, so a failure
            # wiring deps/params onto it must not leave a half-made
            # transform file behind.
            transform_file = _node_dir(node_path) / f"{transform_name}.py"
            if transform_file.is_file():
                transform_file.unlink()
            raise
        self._touched.append(f"{pascal_node_path(node_path)}.transforms.{transform_name}")
        return node_path, transform_name

    def _create_transform_entry(self, entry: str) -> tuple[str, str] | None:
        """One `PathedNodeSignature.transformName<params>(deps)`
        top-level statement — see `_create_transform`."""
        node_path, transform_name, dep_paths, plain_params = parse_pathed_transform_target(entry)
        return self._create_transform(node_path, transform_name, dep_paths or [], plain_params or [])

    def _create_bare_transform_entry(self, node_path: str, entry: str) -> tuple[str, str] | None:
        """One bare "transformName<params>(deps)" entry from `node_path`'s
        own "{...}" transforms block (see `fatass.signature.
        FULL_SIGNATURE`) — see `_create_transform`."""
        transform_name, dep_paths, plain_params = parse_bare_transform_spec(entry, node_path)
        return self._create_transform(node_path, transform_name, dep_paths, plain_params)

    def _modify_created_transforms(
        self, created: list[tuple[str, str] | None], comments: list[str | None]
    ) -> None:
        """`-m`'s own third pass: after every node and transform from the
        first two passes exists, pair each transform actually CREATED
        just now (`created`, one entry per transform occurrence, `None`
        where that occurrence already existed and so was left alone) with
        its own comment (`comments`, from `_extract_transform_comments`
        against the ORIGINAL, un-comment-stripped target text — same
        order, one entry per occurrence, by construction) and, wherever
        both are present, silently `modify` that transform with the
        comment as its prompt. Mirrors `ModifyCommand.run`'s own
        transform branch (extra sys-prompt included) rather than
        reimplementing it."""
        # Local imports: same load-order reasoning as `_touch`'s own.
        from .._internal.prompts import load_topology_edit_system_prompt
        from ..core.free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE
        from ..topology_ops.scaffold import refine_transform
        from .modify import _transform_extra_sys_prompt

        for ref, comment in zip(created, comments):
            if ref is None or not comment:
                continue
            node_path, transform_name = ref
            extra = _transform_extra_sys_prompt(node_path, transform_name)
            refine_transform(
                node_path,
                transform_name,
                comment,
                system_prompt=load_topology_edit_system_prompt("modify", extra=extra),
                permission_mode=DEFAULT_PERMISSION_MODE,
                silent=True,
                model=None,
                tools=DEFAULT_ALLOWED_TOOLS,
            )
            self._modified.append(f"{pascal_node_path(node_path)}.transforms.{transform_name}")

    def run(self, args: argparse.Namespace) -> int:
        self._touched = []
        self._modified = []
        self._pending_transforms = []
        try:
            if args.path is not None:
                if args.target is not None:
                    raise TopologyValidationError(
                        "give either a target argument or -p/--path, not both"
                    )
                file_path = Path(args.path)
                if not file_path.is_file():
                    raise TopologyValidationError(f"{file_path} does not exist")
                target_text = file_path.read_text(encoding="utf-8").strip()
            elif args.target is not None:
                target_text = args.target
            else:
                raise TopologyValidationError(
                    "touch needs either a target argument or -p/--path"
                )

            # Pass 1: create every node from every statement (a node-tree's
            # own recursive subnodes included) before creating ANY
            # transform — a transform's "(deps)" may reference a node
            # declared later in this same call, wherever it appears
            # (another top-level statement, a sibling deeper in the same
            # tree, ...), not just one already created earlier in a naive
            # single top-to-bottom pass. Both the standalone
            # `PathedNodeSignature.transformName<params>(deps)` top-level
            # form and a node's own "{...}" transforms-block entries are
            # deferred into `self._pending_transforms` the same way (see
            # `_touch`), preserving overall discovery order.
            for entry in _split_top_level_statements(_strip_comments(target_text)):
                if _looks_like_transform_target(entry):
                    self._pending_transforms.append(lambda e=entry: self._create_transform_entry(e))
                else:
                    name_or_path, type_name, class_kwargs, child_specs, transform_specs = (
                        _parse_touch_spec(entry)
                    )
                    node_path = resolve_node_path(name_or_path)
                    self._touch(node_path, type_name, class_kwargs, child_specs, transform_specs)

            # Pass 2: every node from pass 1 now exists — safe to create
            # every transform, in the order they were originally found.
            # Each closure's own return value (the (node_path,
            # transform_name) it created, or None if that transform
            # already existed) is kept, in the same order, for pass 3.
            created_transforms = [create_pending_transform() for create_pending_transform in self._pending_transforms]

            # Pass 3 (-m only): pair each transform actually created just
            # now with its own "#" comment, if any, from the ORIGINAL
            # (un-comment-stripped) target text, and silently modify it.
            if args.modify:
                comments = _extract_transform_comments(target_text)
                self._modify_created_transforms(created_transforms, comments)
        except (TopologyValidationError, ValueError) as exc:
            for label in self._touched:
                print(f"{label}: created")
            for label in self._modified:
                print(f"{label}: modified")
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if not self._touched:
            print("already exists (nothing to touch)")
            return 0
        for label in self._touched:
            print(f"{label}: created")
        for label in self._modified:
            print(f"{label}: modified")
        return 0
