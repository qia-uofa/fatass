from .._internal.naming import pascal_case, snake_case
from ..node.chain import Chain
from ..node.dictionary import Dictionary
from ..core.transform import _import_node
from ..errors import TopologyValidationError
from ..resolve.cwd import ROOT, expand
from ..signature import (
    SIMPLE_TYPED,
    _parse_one_named_entry,
    _split_top_level_commas,
    _split_trailing_angle,
    _split_trailing_curly,
    _split_trailing_parens,
    _split_type_suffix,
    _tokenize_space_args,
    pathed_signature,
    validate_node_signature,
)


def resolve_node_path(raw: str, current: str | None = None) -> str:
    """Expand a node-path expression relative to `current` (see
    fatass.resolve.cwd.expand — the actual current node, i.e.
    FATASS_NODE from the dotenv file, unless `current` overrides it —
    "."/".."/"@" navigation, etc.), rejecting ROOT: every command that
    takes a node.path needs an actual node, not the bare topology root.

    `current` lets a caller resolve a path expression relative to some
    OTHER node than the real current one — used for the transform-
    target grammar's own "(deps)" entries (see `_parse_pathed_deps`),
    each resolved relative to the transform's own target node's PARENT
    (not the target node itself, and not wherever the command happens
    to be invoked from) — e.g. "Jrpg.Design.Overview.build(BrainStorm)"
    means "BrainStorm, Overview's own sibling under Design": deps are
    overwhelmingly siblings of the node they feed, so anchoring one
    level up (at the parent) makes THAT the bare, dot-free case, at the
    cost of needing ".." for a dep that's actually a child of the
    transform's own node (rare) instead of a sibling (common).

    No "<NodeType(args)>" signature handling here — this is the shared
    primitive `resolve_and_validate_node_path` (below, for an argument
    naming a node that must already exist) and `parse_create_target`
    (which strips and interprets its OWN such suffix as the type to
    give a not-yet-existing node) both build on; call one of those
    instead wherever the caller knows which of the two it means."""
    node_path = expand(raw, current)
    if node_path == ROOT:
        raise TopologyValidationError(
            f"{raw!r} resolved to the topology root, which isn't a node"
        )
    return node_path


def resolve_and_validate_node_path(raw: str) -> str:
    """`resolve_node_path`, plus an optional trailing "<NodeType(args)>"
    signature assertion (see `fatass.signature.validate_node_signature`)
    against the resolved node, which must already exist — e.g.
    "foo.bar<Chain>" only resolves if "foo.bar" actually is one. Use for
    any argument that names a node which must already exist; a bare
    path (no suffix) behaves exactly as `resolve_node_path` always has."""
    stripped, type_name, expected_sig = _split_type_suffix(raw)
    node_path = resolve_node_path(stripped)
    if type_name is not None:
        validate_node_signature(node_path, type_name, expected_sig, raw)
    return node_path


def parse_node_path(path: str) -> tuple[str, str | None]:
    """"."-separated node/transform path, e.g.
    "node1.node2.transforms.synthesize" -> ("node1.node2", "synthesize"),
    optionally suffixed with "<NodeType(args)>" (e.g.
    "node1.node2<Chain>") to assert the node's actual type — see
    `resolve_and_validate_node_path`. The suffix is stripped before the
    "."-splitting above, so it never gets mistaken for part of the
    transform name.

    Unrelated to the `PathedNodeSignature.transformName` grammar below
    (this is `run`'s own, pre-existing "dive into a named transform"
    dotted-access convention, not a target that names a transform to
    create/modify/apply/bind/unbind/debug/remove — left as-is)."""
    stripped, type_name, expected_sig = _split_type_suffix(path)
    parts = stripped.split(".")
    if len(parts) >= 2 and parts[-2] == "transforms":
        node_path, transform_name = ".".join(parts[:-2]), parts[-1]
    else:
        node_path, transform_name = stripped, None
    node_path = resolve_node_path(node_path)
    if type_name is not None:
        validate_node_signature(node_path, type_name, expected_sig, path)
    return node_path, transform_name


# --- The transform-target grammar: PathedNodeSignature.transformName ------
#
#     PathedNodeSignature.transformName<params>(deps)
#
# Replaces the older "<transform>(deps)@<node.path>"/"<transform>@<node.path>"
# forms entirely, across `create`, `modify`, `apply`, `bind`, `unbind`,
# `debug`, and `remove` — a transform is now addressed the way an OOP
# method call reads: the node it belongs to, PascalCase (matching that
# node's own real class name, not its snake_case topology-path segment),
# then a "." and the transform's own name, lowerCamelCase ("node always
# begins with cap and transform lowercase"). `PathedNodeSignature`'s own
# navigation (a leading "@", "."/".." hops, a "[idx]" chain-index
# suffix) is exactly `resolve_node_path`'s — only the actual name
# segments get PascalCase-checked/converted, via the same `snake_case()`
# `touch` already uses to turn a child's class name back into its
# directory name.
#
# `<params>` (plain typed parameters, e.g. "n:int=5") and "(deps)"
# (comma-separated PathedNodeSignatures, each optionally carrying its
# own "<NodeType>" assertion) are both independently omittable, each
# defaulting to empty when omitted — "Node.transform<params>" alone
# means "Node.transform<params>()"; "Node.transform" alone means no
# params and no deps at all. Each dep's own navigation is relative to
# the transform's own node's PARENT, not the node itself — e.g.
# "Jrpg.Design.Overview.build(BrainStorm)" means "BrainStorm, a sibling
# of Overview under Design" with no ".." needed, since a dep is almost
# always a sibling of the node it feeds.


def _validate_camel_transform_name(raw: str, target: str) -> str:
    """Validate `raw` (the grammar's own trailing transform-name
    segment) starts with a lowercase letter — "transform lowercase",
    the counterpart to `_pascal_path_to_snake`'s node-segment rule —
    then convert it via the same `snake_case()` to the real function/
    file name (e.g. a hypothetical "buildAssets" becomes "build_assets";
    a single already-lowercase word like "build" is unaffected)."""
    if not raw or not raw[0].isalpha() or not raw[0].islower():
        raise TopologyValidationError(
            f"{target!r}: transform name {raw!r} must start with a "
            f"lowercase letter"
        )
    return snake_case(raw)


def _split_transform_target_suffix(raw: str) -> tuple[str, str | None, str | None]:
    """Peel the transform-target grammar's optional trailing "(deps)"
    (outermost) and/or "<params>" (just before it) off `raw` —
    (prefix, params_raw_or_None, deps_raw_or_None). `prefix` is still
    the unsplit "PathedNodeSignature.transformName".

    Also peels (and discards) a trailing "{...}" in between, if one is
    there — never true for a genuine standalone transform target (which
    has no such block of its own), but `_looks_like_transform_target`
    calls this on ANY top-level `touch` statement to decide whether it's
    one at all, including a full node-tree entry whose own "{...}"
    transforms block (see `fatass.signature.FULL_SIGNATURE`) can contain
    dots of its own (e.g. a dep reference like "MyNode.Sibling") that
    would otherwise fool the naive `.rpartition(".")` `_looks_like_
    transform_target` does on what's left — peeling it away first keeps
    those inner dots from ever reaching that check."""
    text = raw.strip()
    prefix, deps_raw = _split_trailing_parens(text)
    prefix, _transforms_raw = _split_trailing_curly(prefix)
    prefix, params_raw = _split_trailing_angle(prefix)
    return prefix, params_raw, deps_raw


def _looks_like_transform_target(raw: str) -> bool:
    """True if `raw` looks like the `PathedNodeSignature.transformName`
    grammar rather than a plain node.path — e.g. `create`'s own bare
    "node.path<NodeSubclass ...>" node-creation form. Every real
    segment is PascalCase in BOTH forms now (a plain node.path is no
    longer snake_case either — see `fatass.resolve.cwd.expand`), so
    there are two signals, checked in order:

    1. An explicit trailing "(deps)" is unambiguous on its own,
       regardless of the transform-name segment's own case — plain
       node-creation never uses parens at all, only its own
       `<NodeSubclass ...>` suffix. This also means a badly-cased
       attempt like "Node.Build()" is still correctly routed to the
       transform grammar (where `_validate_camel_transform_name`
       raises a clear "must be lowercase" error), instead of being
       silently misparsed as plain node creation with a literal "()"
       baked into the path.
    2. Otherwise (no parens — a bare "Node.transform" or
       "Node.transform<params>"), the only remaining signal is the
       very LAST segment's own case: lowerCamelCase means it's a
       transform name (a transform target); PascalCase means it's the
       plain node's own new/referenced name (not a transform target).

    A `raw` with no "." at all (a bare name) is never a transform
    target — a transform target always needs both a node AND a
    transform name."""
    prefix, _params_raw, deps_raw = _split_transform_target_suffix(raw)
    _node_part, sep, transform_part = prefix.rpartition(".")
    if not sep or not transform_part:
        return False
    if deps_raw is not None:
        return True
    return transform_part[0].islower()


def _parse_pathed_deps(raw: str, *, relative_to: str) -> list[str]:
    """The transform-target grammar's own "(deps)" content: a comma-
    separated list of `PathedNodeSignature`s, each optionally carrying
    its own trailing "<NodeType(args)>"-style assertion (checked
    against the already-existing dependency — see
    `resolve_and_validate_node_path`, whose job this mirrors; the
    PascalCase-to-snake_case conversion itself happens automatically
    inside `resolve_node_path`/`expand`, same as for any other node.path).

    Each dep's own navigation is relative to `relative_to` — the
    transform's own TARGET node's PARENT (not the target node itself,
    and not whatever the real current node happens to be) — e.g.
    "Jrpg.Design.Overview.build(BrainStorm)" means "BrainStorm, a
    sibling of Overview under Design" with no ".." needed at all,
    since deps are overwhelmingly siblings; a dep that's a child of the
    transform's own node instead needs its own leading ".." to get back
    down to it. A leading "@" in a dep still overrides this and goes
    absolute, same as ever."""
    dep_paths: list[str] = []
    for item in _split_top_level_commas(raw):
        stripped, type_name, expected_sig = _split_type_suffix(item)
        node_path = resolve_node_path(stripped, current=relative_to)
        if type_name is not None:
            validate_node_signature(node_path, type_name, expected_sig, item)
        dep_paths.append(node_path)
    return dep_paths


def _parse_transform_params(raw: str, target: str) -> list[tuple[str, str]]:
    """The transform-target grammar's own "<params>" content: space-
    separated `name:type=value`/`name:type`/`name=value`/bare-`name`
    entries — the exact same grammar a node's own named/typed type-args
    already use (see `_parse_one_named_entry`/`_tokenize_space_args`) —
    converted into the (param_name, type_annotation) shape
    `topology_ops.bind.add_plain_params` expects, `type_annotation`
    itself carrying an "=default" suffix as raw text (see that module's
    own `_param_text`) — but ONLY when this entry actually had a
    literal "=" somewhere in it. `_parse_one_named_entry` can't itself
    distinguish "no default given" from "default explicitly given as
    empty" (both come back as value "") — fine for a node's own class
    attribute (which always needs SOME concrete default), wrong for a
    transform's plain parameter (a bare "n:int" must stay a required
    parameter, not silently gain a bogus "=''' default) — so this
    checks for a literal "=" in the raw token itself instead of
    trusting that returned value alone."""
    plain_params: list[tuple[str, str]] = []
    for token in _tokenize_space_args(raw, target):
        name, type_str, value_str = _parse_one_named_entry(token, target)
        if "=" in token:
            plain_params.append((name, f"{type_str}={value_str}"))
        else:
            plain_params.append((name, type_str))
    return plain_params


def parse_pathed_transform_target(
    raw: str,
) -> tuple[str, str, list[str] | None, list[tuple[str, str]] | None]:
    """The transform-target grammar in full:
    "PathedNodeSignature.transformName<params>(deps)" — see the module-
    level comment above for the full shape.

    Returns (node_path, transform_name, dep_paths, plain_params) —
    `dep_paths`/`plain_params` are `None` when their own bracket group
    was omitted from `raw` ENTIRELY (as opposed to given but empty,
    e.g. an explicit "()"/"<>") — a caller that only ever CREATES
    (never needs the None-vs-empty distinction, e.g. `create`/`touch`)
    can safely treat `None` the same as an empty list; a caller that
    VERIFIES an existing signature (`modify`) needs the distinction, to
    know whether to skip verification entirely."""
    prefix, params_raw, deps_raw = _split_transform_target_suffix(raw)
    node_part, sep, transform_part = prefix.rpartition(".")
    if not sep:
        raise ValueError(
            f"expected PathedNodeSignature.transformName, got {raw!r}"
        )
    transform_name = _validate_camel_transform_name(transform_part, raw)
    node_path = resolve_node_path(node_part)
    parent_path = node_path.rsplit(".", 1)[0] if "." in node_path else ROOT

    dep_paths = (
        _parse_pathed_deps(deps_raw, relative_to=parent_path) if deps_raw is not None else None
    )
    plain_params = _parse_transform_params(params_raw, raw) if params_raw is not None else None
    return node_path, transform_name, dep_paths, plain_params


def parse_bare_transform_spec(raw: str, node_path: str) -> tuple[str, list[str], list[tuple[str, str]]]:
    """One entry inside `node_path`'s own "{...}" transforms block (see
    `fatass.signature.FULL_SIGNATURE`/`commands.touch`'s full-signature
    support) — "transformName<params>(deps)", with no node-path prefix
    at all, unlike the standalone `PathedNodeSignature.transformName
    <params>(deps)` grammar `parse_pathed_transform_target` handles: the
    node is already known here (whichever node's own "{...}" block this
    entry came from), so there's no "." to split a node part off of —
    `raw` is the transform name (plus its own brackets) alone. Otherwise
    the exact same grammar/actions, reused via the same private helpers
    rather than reimplemented — deps still resolved relative to
    `node_path`'s own PARENT (not `node_path` itself), same convention
    as ever.

    Returns (transform_name, dep_paths, plain_params) — unlike
    `parse_pathed_transform_target`, an omitted bracket comes back as an
    empty list, not `None`: a "{...}" transforms-block entry is always a
    CREATE (`touch`'s only use for this grammar), which never needs the
    None-vs-empty distinction `modify`'s verification does."""
    prefix, params_raw, deps_raw = _split_transform_target_suffix(raw)
    transform_name = _validate_camel_transform_name(prefix, raw)
    parent_path = node_path.rsplit(".", 1)[0] if "." in node_path else ROOT

    dep_paths = _parse_pathed_deps(deps_raw, relative_to=parent_path) if deps_raw is not None else []
    plain_params = _parse_transform_params(params_raw, raw) if params_raw is not None else []
    return transform_name, dep_paths, plain_params


def parse_transform_target(raw: str) -> tuple[str, str]:
    """"PathedNodeSignature.transformName" -> (node_path, transform_name)
    — for `apply`/`bind`/`unbind`/`debug`, whose own target grammar
    never itself carries "<params>"/"(deps)" (`apply` takes `key=value`
    context args separately; `bind`/`unbind` take dep paths as their
    own separate positional arguments) — reuses
    `parse_pathed_transform_target` and discards its dep_paths/
    plain_params (always `None`, since neither bracket is ever given
    here)."""
    node_path, transform_name, _dep_paths, _plain_params = parse_pathed_transform_target(raw)
    return node_path, transform_name


def parse_maybe_transform_target(raw: str) -> tuple[str, str | None]:
    """Like `parse_transform_target`, but a bare node.path (no
    transform at all) is valid too — for `remove`, whose target may
    name either a whole node or just one of its transforms. Detected
    via `_looks_like_transform_target` (the PascalCase-before-final-dot
    heuristic); a bare node.path is validated/resolved via
    `resolve_and_validate_node_path` (its own optional trailing
    "<NodeType(args)>" assertion still works, same as ever)."""
    if _looks_like_transform_target(raw):
        return parse_transform_target(raw)
    return resolve_and_validate_node_path(raw), None


def parse_modify_target(
    target: str,
) -> tuple[str, str | None, list[str] | None, list[tuple[str, str]] | None]:
    """`modify`'s own target: a bare node.path (its own class file), or
    the transform-target grammar naming one of its transforms —
    optionally with its own "<params>(deps)" to VERIFY (not create)
    against the transform's actual current signature before modifying
    it.

    Returns (node_path, transform_name, dep_paths, plain_params).
    `dep_paths`/`plain_params` are `None` when neither bracket was
    given at all (a bare "Node.transform" or plain node.path target) —
    the caller should skip signature verification in that case; when
    either was given (even empty), both come back as real (possibly
    empty) lists, checked by the caller against the transform's actual
    current signature — `modify` raises if they don't match, since a
    stale or typo'd bracket would otherwise be silently ignored.

    The plain node.path form may also carry its own trailing
    "<NodeType(args)>" assertion, e.g. "node.path<Chain>" — see
    `resolve_and_validate_node_path`."""
    if not _looks_like_transform_target(target):
        return resolve_and_validate_node_path(target), None, None, None
    return parse_pathed_transform_target(target)


def parse_create_target(
    target: str,
) -> tuple[str, str | None, str, list[str], list[tuple[str, str]], dict[str, tuple]]:
    """`create`'s own target: either

    - a plain node.path, optionally suffixed with "<NodeSubclass ...>"
      — e.g. "Members<Chain>" — naming the `fatass.<NodeSubclass>` base
      class a newly-created node should subclass instead of the default
      `fatass.Node`, itself optionally followed by its own space-
      separated constructor-style args (see
      `fatass.signature._parse_type_args`) — the exact same shape
      `fatass.signature`'s `Node._type_args()` renders a node's
      existing signature in, so copy-pasting one is always valid input
      here: field names as bare space-separated identifiers, and/or
      (for an Array subclass) `dim=<int>x<int>x...` — e.g. "MyNode
      <SingleCsv field1 field2>" bakes `FIELDS = ("field1", "field2")`
      onto the class, written as that Single's header row on creation;
      "Grid<ArrayCsv field1 field2 dim=2x2x2>" bakes both `FIELDS` and
      `DIM = (2, 2, 2)` — baked in immediately (see
      `scaffold.create_node`'s `class_kwargs`), before `on_created()`
      runs, so the node's shape is known right away rather than left
      for `on_created()` to guess. This node.path is PascalCase, same
      as everywhere else (`fatass.resolve.cwd.expand` enforces/converts
      it universally) — the node's own NEW name, chosen by the caller,
      not (yet) an existing class's.

    - the transform-target grammar (see the module-level comment
      above), to create a transform instead — e.g.
      "Jrpg.Design.Overview.build(Jrpg.Design.BrainStorm)". Its own
      "(deps)" entries are bound the same way as `bind` (a
      deterministic operation, not an agent call); its own "<params>"
      entries are added as ordinary, import-free parameters with that
      annotation — no binding. A plain parameter's type may itself
      carry a "=default" suffix — e.g. "n:int=0" — to give it a default
      value; see `topology_ops.bind._param_text` for exactly how that's
      turned into real Python. Distinguished from the plain node-
      creation form via `_looks_like_transform_target` — mutually
      exclusive with the "<NodeSubclass>" suffix (that one only applies
      to a bare node target).

    Returns (node_path, transform_name, base_class, dep_node_paths,
    plain_params, class_kwargs) — the last three always falsy except
    for their own respective forms above. Only used by `create`/`touch`
    — every other command's targets don't create nodes."""
    if _looks_like_transform_target(target):
        node_path, transform_name, dep_paths, plain_params = parse_pathed_transform_target(target)
        return node_path, transform_name, "Node", dep_paths or [], plain_params or [], {}

    stripped, type_name, class_kwargs = _split_type_suffix(target)
    base_class = type_name if type_name is not None else "Node"
    node_path = resolve_node_path(stripped)
    return node_path, None, base_class, [], [], class_kwargs


def resolve_move_target(raw_new: str, old_path: str) -> str:
    """`move`/`copy`'s destination argument, with a trailing "*" segment
    substituted for `old_path`'s own leaf name — e.g. "node2.*" (with
    `old_path` "node1") resolves the same as "node2.node1": reparent
    under node2, keeping the same name, mirroring Unix `mv file dir/`
    ("move node1 into node2, same name"). A bare "*" alone means "same
    name, at the current node" — resolved from whatever `raw_new` would
    otherwise expand from (still goes through `resolve_node_path`, so
    "."/".."/"@" navigation before the "*" still works, e.g.
    "node2..*"). Only the trailing segment may be "*" — a literal node
    named "*" isn't otherwise expressible (not a valid Python
    identifier), so this substitution is unambiguous."""
    if raw_new == "*" or raw_new.endswith(".*"):
        # old_path is already-resolved (real, snake_case) -- PascalCase
        # it back before splicing it into raw_new, which still needs to
        # satisfy resolve_node_path's own PascalCase requirement.
        stem = pascal_case(old_path.rsplit(".", 1)[-1])
        raw_new = stem if raw_new == "*" else f"{raw_new[:-1]}{stem}"
    return resolve_node_path(raw_new)


def resolve_chain(raw: str) -> type[Chain]:
    """`raw` (a node.path expression, resolved via
    resolve_and_validate_node_path() — so it may carry its own
    "<Chain>"/"<Chain(...)>" assertion, redundant with the check just
    below but harmless) imported as an actual `Chain` subclass — used by
    `len`/`insert`/`push`/`pop`, which operate on the list itself (never
    an indexed item — those take `n` as a plain argument, not `[N]`
    bracket syntax). Raises if there's no such node, or it isn't a
    Chain."""
    node_path = resolve_and_validate_node_path(raw)
    node_cls = _import_node(node_path)
    if not issubclass(node_cls, Chain):
        raise TopologyValidationError(
            f"{pathed_signature(node_path, SIMPLE_TYPED, max_depth=0)} is not a Chain"
        )
    return node_cls


def resolve_dictionary(raw: str) -> type[Dictionary]:
    """`raw` (a node.path expression, resolved via
    resolve_and_validate_node_path()) imported as an actual `Dictionary`
    subclass — used by `dict keys`/`set`/`pop`, which operate on the
    dictionary itself (never an indexed entry — those take `key` as a
    plain argument, not `[key]` bracket syntax). Raises if there's no
    such node, or it isn't a Dictionary."""
    node_path = resolve_and_validate_node_path(raw)
    node_cls = _import_node(node_path)
    if not issubclass(node_cls, Dictionary):
        raise TopologyValidationError(
            f"{pathed_signature(node_path, SIMPLE_TYPED, max_depth=0)} is not a Dictionary"
        )
    return node_cls


def parse_kv_args(pairs: list[str]) -> dict[str, str]:
    context = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        context[key] = value
    return context
