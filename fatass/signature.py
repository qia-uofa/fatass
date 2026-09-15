"""Formal node "signature" grammar and renderer.

    NodeClassName<NodeType argument1 argument2>(SubNodeSignature1,SubNodeSignature2,...)

`NodeClassName` is the node's own Python class name (PascalCase, valid
Python identifier — e.g. "Lectures"), never the lowercase topology-path/
directory segment ("lectures") that names it as an attribute. `NodeType`
is the fatass base kind it's built on (Chain/Single/Tuple/Array/Node/...,
`Node._base_kind()`'s own name); `argument1 argument2` are that base
kind's own constructor-like arguments (`Node._type_args()` — a Tuple's
`FIELDS`, an Array's `FIELDS`/`DIM`), space-separated — one grammar for
every argument kind (a bare field name, `dim=RxCx...`, a `Dir`'s path, or
a named/typed `name:type=value` param), any entry quoted (double quotes,
`\\"`/`\\\\` escapes) if it needs to contain whitespace itself (a `Dir`
path, or a param's value) — there is no separate comma-parenthesized
form.

Every piece past the bare class name is an omission the grammar allows,
each with an implied default that only matters when the signature
describes/creates a node that doesn't exist yet (as in `fatass create`'s
own `name<NodeSubclass dim=...>` syntax) — omitted arguments default to
`()`, an omitted type defaults to plain `Node()`, omitted subnodes
default to none declared. Rendering an *existing* node (this module's
only job) never fabricates those defaults back in: an omitted piece is
simply not printed.

Two independent axes, each with three "degrees":

    typing degree     1 = none    (bare `NodeClassName`)
                       2 = simple  (`NodeClassName<NodeType>`)
                       3 = full    (`NodeClassName<NodeType args>`)

    structure degree   4 = simple  (`(...)` holds each subnode's bare,
                                    degree-1 class name — one level,
                                    no further recursion)
                       5 = full    (`(...)` holds each subnode's own
                                    complete signature, recursed all
                                    the way down)

    (there is no bare structure degree — a node with no `(...)` at all
    is just whatever its typing-degree-alone signature already is: 1,
    2, or 3)

A signature can also apply a *different* typing degree to this node
itself (`self_degree`, "xxx-typed-based") than to every node beneath it
("yyy-typed", applied uniformly/propagated at every depth below the
top) — `self_degree == descendant_degree` is the plain "AxB" form
(typing degree propagates unchanged); they may differ, and either one
(but not both at once — that's just the untyped degree-5 form already
covered on its own) may be the "none" degree.
"""

import dataclasses
import inspect
import itertools
import re
from typing import Literal, get_type_hints

from ._internal.naming import pascal_node_path
from .core.transform import _import_node, discover
from .errors import TopologyValidationError
from .ls import _direct_subnodes
from .node.node import _quote_param_value_if_needed
from .resolve.cwd import PAREN_ROOT, ROOT

Degree = Literal[1, 2, 3]
_DEGREE_NAME = {1: "none", 2: "simple", 3: "full"}


@dataclasses.dataclass(frozen=True)
class SignatureConfig:
    show_type: bool = True
    """Show `<NodeType...>` at all. False = degree 1 (bare class name)."""
    show_args: bool = True
    """Only meaningful when `show_type` is True: True = degree 3 (show
    ` argument1 argument2 ...`), False = degree 2 (bare `<NodeType>`)."""
    show_subnodes: bool = True
    """Show the trailing `(...)` of subnode signatures at all — the
    structure-degree-4-or-5 vs. no-`(...)` distinction."""
    show_class_name: bool = True
    """False omits the leading `NodeClassName` entirely, leaving just
    `<NodeType args>` (and/or `(...)`) — for a caller that already shows
    the class name somewhere else (e.g. a PlantUML class box's own
    header) and just wants the rest as a separate line/label."""
    show_transforms: bool = False
    """Show this node's own transforms as a `{transform1<params>(deps);
    transform2<params>(deps);}` block, right before the `(...)` subnode
    block — see `TransformSigData`/`_render_transform_sig`. Off by
    default (every pre-existing preset is unaffected); `FULL_SIGNATURE`
    below is the one that turns it on. Propagates to descendants exactly
    like every other flag here, via `child_config`/`for_child()`."""
    child_config: "SignatureConfig | None" = None
    """Config used to render each direct subnode's own signature inside
    `(...)`. `None` (the default) reuses this same config — i.e. this
    node's own typing degree is *propagated* to every descendant
    (structure degree 5, "AxA"). A different, `show_subnodes=False`
    config here gives structure degree 4 (subnodes shown only as their
    own bare class name, one level, no further recursion). A config
    with a *different* typing degree (but itself propagating via its
    own `child_config=None`) gives the "xxx-typed-based yyy-typed"
    mixed form."""

    def for_child(self) -> "SignatureConfig":
        return self.child_config if self.child_config is not None else self


def degree_config(
    degree: Degree, *, show_subnodes: bool, child_config: SignatureConfig | None = None
) -> SignatureConfig:
    """One typing degree (1/2/3), with `(...)` shown or not, and an
    explicit (or self-propagating, if omitted) child config."""
    if degree == 1:
        return SignatureConfig(show_type=False, show_subnodes=show_subnodes, child_config=child_config)
    if degree == 2:
        return SignatureConfig(
            show_type=True, show_args=False, show_subnodes=show_subnodes, child_config=child_config
        )
    if degree == 3:
        return SignatureConfig(
            show_type=True, show_args=True, show_subnodes=show_subnodes, child_config=child_config
        )
    raise ValueError(f"degree must be 1, 2 or 3, got {degree!r}")


def mixed_full_structured(self_degree: Degree, descendant_degree: Degree) -> SignatureConfig:
    """"xxx-typed-based yyy-typed full-structured" — this node shown at
    `self_degree`, every node beneath it (uniformly, at every depth)
    shown at `descendant_degree`. `self_degree == descendant_degree`
    collapses to the plain propagated "AxA" (structure-degree-5) form;
    both degrees being 1 (`none`) collapses to the already-named plain
    untyped full-structured signature (`FULL_STRUCTURED` below) — this
    function doesn't stop you from asking for that redundant case, it
    just isn't one of the presets registered under a "based" name."""
    descendant_config = degree_config(descendant_degree, show_subnodes=True)  # propagates itself
    return degree_config(self_degree, show_subnodes=True, child_config=descendant_config)


# ---- 1-5: the base forms --------------------------------------------------

BASE = degree_config(1, show_subnodes=False)
"""1. `NodeClassName` — no type, no subnodes."""

SIMPLE_TYPED = degree_config(2, show_subnodes=False)
"""2. `NodeClassName<NodeType>`."""

FULL_TYPED = degree_config(3, show_subnodes=False)
"""3. `NodeClassName<NodeType argument1 argument2>`."""

SIMPLE_STRUCTURED = degree_config(1, show_subnodes=True, child_config=BASE)
"""4. `NodeClassName(SubNodeClassName,...)` — untyped self, subnodes
shown only as their own bare class name (degree 1), not recursed."""

FULL_STRUCTURED = degree_config(1, show_subnodes=True)
"""5. `NodeClassName(SubNodeSignature,...)` — untyped self, every
subnode shown with its own full (degree-1, structure-degree-5)
signature, recursed all the way down."""

# ---- 6: typed simple-structured (2x4, 3x4) --------------------------------

SIMPLE_TYPED_SIMPLE_STRUCTURED = degree_config(2, show_subnodes=True, child_config=BASE)
"""2x4. `NodeClassName<NodeType>(SubNodeClassName,...)`."""

FULL_TYPED_SIMPLE_STRUCTURED = degree_config(3, show_subnodes=True, child_config=BASE)
"""3x4. `NodeClassName<NodeType args>(SubNodeClassName,...)`."""

# ---- 7: typed full-structured, propagated (2x5, 3x5) ----------------------

SIMPLE_TYPED_FULL_STRUCTURED = degree_config(2, show_subnodes=True)
"""2x5. `NodeClassName<NodeType>(...)`, same degree-2 typing recursed
(propagated) at every depth."""

FULL_TYPED_FULL_STRUCTURED = degree_config(3, show_subnodes=True)
"""3x5. `NodeClassName<NodeType args>(...)`, same degree-3 typing
recursed (propagated) at every depth — the "everything, everywhere"
signature."""

FULL_SIGNATURE = dataclasses.replace(FULL_TYPED_FULL_STRUCTURED, show_transforms=True)
"""The "full signature config" — `FULL_TYPED_FULL_STRUCTURED` plus each
node's own transforms as a `{transform1<params>(deps);...}` block (see
`SignatureConfig.show_transforms`), propagated to every descendant the
same way the typing/structure degrees already are (`child_config=None`).
`NodeClassName<NodeType args>{transform1<params>(deps);...}(...)` —
round-trips through `fatass touch` not just node/subnode structure but
the transforms wired onto each node too, since `show_transforms`
requires `build_sig_data(..., with_transforms=True)` to actually gather
them (done automatically by `signature()`/`pathed_signature()`)."""

# ---- 8: typed full-structured, self degree "based" a different,          --
#         propagated descendant degree (every asymmetric xxx/yyy pair,     --
#         excluding both == "none")                                       --

PRESETS: dict[str, SignatureConfig] = {
    "base": BASE,
    "simple_typed": SIMPLE_TYPED,
    "full_typed": FULL_TYPED,
    "simple_structured": SIMPLE_STRUCTURED,
    "full_structured": FULL_STRUCTURED,
    "simple_typed_simple_structured": SIMPLE_TYPED_SIMPLE_STRUCTURED,  # 2x4
    "full_typed_simple_structured": FULL_TYPED_SIMPLE_STRUCTURED,  # 3x4
    "simple_typed_full_structured": SIMPLE_TYPED_FULL_STRUCTURED,  # 2x5
    "full_typed_full_structured": FULL_TYPED_FULL_STRUCTURED,  # 3x5
    "full_signature": FULL_SIGNATURE,
}

for _self_degree, _descendant_degree in itertools.product((1, 2, 3), repeat=2):
    if _self_degree == 1 and _descendant_degree == 1:
        continue  # both "none" — that's just FULL_STRUCTURED, not a "based" form
    if _self_degree == _descendant_degree:
        continue  # not "mixed" — already named above as the propagated AxA form
    _name = (
        f"{_DEGREE_NAME[_self_degree]}_typed_based_"
        f"{_DEGREE_NAME[_descendant_degree]}_typed_full_structured"
    )
    PRESETS[_name] = mixed_full_structured(_self_degree, _descendant_degree)

del _self_degree, _descendant_degree, _name


# ---- gathering + rendering -------------------------------------------------


@dataclasses.dataclass
class TransformSigData:
    """One transform's own signature-relevant facts — the `{...}`
    transforms-block counterpart to `NodeSigData`, gathered by
    `_gather_transform_sig_data`."""

    name: str
    type_args: list[str]
    """This transform's own `<params>` entries — its plain (non-`Node`)
    parameters, each already rendered `name:type` / `name:type=value`
    (quoted if needed — see `_quote_param_value_if_needed`), same textual
    shape as a node's own named type-args."""
    dep_paths: list[str]
    """Absolute topology path of each `Node`-typed parameter, in
    declaration order — for `(deps)`, always identified by path (never
    bare class name), since a dependency can live anywhere."""


@dataclasses.dataclass
class NodeSigData:
    """A node's own signature-relevant facts, gathered once so
    `render_signature` can be called with several different configs
    (e.g. to print every preset for the same node) without re-walking
    the topology each time."""

    path: str
    class_name: str
    node_type: str
    type_args: list[str]
    children: list["NodeSigData"]
    transforms: list[TransformSigData] = dataclasses.field(default_factory=list)
    """Empty unless gathered via `build_sig_data(..., with_transforms=True)`
    — see `SignatureConfig.show_transforms`."""


def _gather_transform_sig_data(node_path: str) -> list[TransformSigData]:
    """Every transform directly on `node_path`, in the `{...}`
    transforms-block shape (see module docstring) — reuses
    `core.transform.discover()` (the same walk `fatass.ls`/`fatass.graph`
    already use for a node's transforms) rather than a separate
    rediscovery, sorted the same way `fatass.ls.list_node` sorts them
    (any transform literally named "build" first)."""
    specs = sorted(discover(node_path), key=lambda spec: spec.name != "build")
    result = []
    for spec in specs:
        hints = get_type_hints(spec.func)
        type_args = []
        for name, param in spec.context_params.items():
            hint = hints.get(name)
            type_name = hint.__name__ if isinstance(hint, type) else getattr(hint, "__name__", str(hint))
            if param.default is inspect.Parameter.empty:
                type_args.append(f"{name}:{type_name}")
            else:
                value = _quote_param_value_if_needed(str(param.default))
                type_args.append(f"{name}:{type_name}={value}")
        dep_paths = [dep_cls._topology_path() for dep_cls in spec.dependencies.values()]
        result.append(TransformSigData(name=spec.name, type_args=type_args, dep_paths=dep_paths))
    return result


def build_sig_data(
    node_path: str, *, max_depth: int | None = None, with_transforms: bool = False
) -> NodeSigData:
    """Walk `node_path` and its subnodes, gathering the facts
    `render_signature` needs. Raises `TopologyValidationError` (via
    `_import_node`) if `node_path` doesn't exist.

    `max_depth` bounds the recursion (measured from `node_path` itself,
    at depth 0): `None` (the default) recurses unbounded, all the way
    down; `0` returns this one node's own facts with `children=[]` (no
    recursion at all — for a caller that only needs this single node,
    e.g. `graph.py`'s per-node call inside a loop already over every
    node in the topology, where unbounded recursion at each one would be
    an O(n) walk repeated O(n) times); `1` fetches direct children's own
    facts but doesn't recurse into *their* children (matches `ls`'s
    one-level, non-recursive node summary).

    `with_transforms` gathers each node's own transforms too (see
    `TransformSigData`) — off by default, since it costs a real
    `discover()`/`get_type_hints()` walk most callers don't need;
    propagated uniformly to every descendant when set (there's no
    equivalent to `SignatureConfig`'s own per-depth `child_config` here
    — this is a plain bool, not a config, so "gather transforms at depth
    2 but not depth 1" isn't a case this supports)."""
    node_cls = _import_node(node_path)
    next_depth = None if max_depth is None else max_depth - 1
    children = (
        [
            build_sig_data(f"{node_path}.{name}", max_depth=next_depth, with_transforms=with_transforms)
            for name in _direct_subnodes(node_path)
        ]
        if max_depth is None or max_depth > 0
        else []
    )
    return NodeSigData(
        path=node_path,
        class_name=node_cls.__name__,
        node_type=node_cls._base_kind().__name__,
        type_args=node_cls._type_args(),
        children=children,
        transforms=_gather_transform_sig_data(node_path) if with_transforms else [],
    )


def render_signature(
    data: NodeSigData,
    config: SignatureConfig = FULL_TYPED_FULL_STRUCTURED,
    *,
    pathed: bool = False,
    pretty: bool = False,
    _depth: int = 0,
) -> str:
    """`NodeClassName<NodeType arg1 arg2 ...>(child1,child2,...)` — one
    space-separated argument grammar for every `data.type_args` entry
    (a bare field name, `dim=RxCx...`, a `Dir`'s path, or a named/typed
    `name:type=value` param — see `Node._type_args()`), per `config`
    (and `config.for_child()` for each child, recursively). Each entry
    is already rendered exactly as it should appear (quoted by
    `Node._type_args()`/`_quote_param_value_if_needed` if it needs to
    contain whitespace) — this just joins them with plain spaces, and
    this must match `create`'s own parser exactly
    (`fatass.signature._split_type_suffix`), or a node's own rendered
    signature would no longer be valid input to recreate/assert it —
    this module's whole point.

    `pathed=True` identifies every node shown (self and, if the config
    recurses into them, every descendant) by its topology path
    (`@<path>`, or `(@)` for the true root) instead of by class name —
    for a node that isn't a locally-nested child (a transform's
    dependency can live anywhere), where only a path says *which* node
    is meant.

    `pretty=True` breaks a children block across multiple lines, one
    child per line, indented 4 spaces per nesting level (`_depth` — an
    internal recursion counter, never passed by an outside caller) —
    the same layout a hand-written `.sig` file already uses, for a
    large/deep tree (`ls -r`'s own use) that's otherwise an unreadable
    single dense line. The one-line form (`pretty=False`, the default)
    is unaffected, and still round-trips as valid `touch`/`create`
    input either way — pretty-printing only adds whitespace exactly
    where the grammar already tolerates it freely.

    `config.show_transforms` (see `FULL_SIGNATURE`) additionally renders
    this node's own transforms as a `{transform1<params>(deps);
    transform2<params>(deps);}` block, right before the `(...)` subnode
    block — see `_render_transform_sig`. Every entry gets its own
    trailing ";" (including the last), a statement-list convention
    (deliberately unlike the comma-separated `(...)`/`<...>` groups),
    so appending a new entry by hand never needs to touch the one before
    it."""
    if config.show_class_name:
        out = (f"{ROOT}{pascal_node_path(data.path)}" if data.path else PAREN_ROOT) if pathed else data.class_name
    else:
        out = ""
    if config.show_type:
        out += f"<{data.node_type}"
        if config.show_args and data.type_args:
            out += " " + " ".join(data.type_args)
        out += ">"
    if config.show_transforms and data.transforms:
        # A transform's own "(deps)" are always parsed back in relative
        # to ITS NODE'S PARENT (see `commands._targets
        # .parse_bare_transform_spec`) — the anchor for `_relative_dep_
        # expr` below has to match that exactly, or a rendered "{...}"
        # block wouldn't round-trip through `touch` back to the same
        # deps it started with.
        anchor = data.path.rsplit(".", 1)[0] if "." in data.path else ROOT
        if pretty:
            inner_indent = "    " * (_depth + 1)
            closing_indent = "    " * _depth
            rendered_transforms = "\n".join(
                inner_indent + _render_transform_sig(t, anchor) + ";" for t in data.transforms
            )
            out += f"{{\n{rendered_transforms}\n{closing_indent}}}"
        else:
            rendered_transforms = "".join(_render_transform_sig(t, anchor) + ";" for t in data.transforms)
            out += f"{{{rendered_transforms}}}"
    if config.show_subnodes and data.children:
        child_config = config.for_child()
        if pretty:
            inner_indent = "    " * (_depth + 1)
            closing_indent = "    " * _depth
            rendered_children = ",\n".join(
                inner_indent
                + render_signature(child, child_config, pathed=pathed, pretty=True, _depth=_depth + 1)
                for child in data.children
            )
            out += f"(\n{rendered_children}\n{closing_indent})"
        else:
            rendered_children = ",".join(
                render_signature(child, child_config, pathed=pathed) for child in data.children
            )
            out += f"({rendered_children})"
    return out


def _relative_dep_expr(dep_path: str, anchor: str) -> str:
    """The shortest dot-navigation expression that resolves back to
    `dep_path` when parsed relative to `anchor` — the exact inverse of
    how a transform's own "(deps)" are actually resolved (relative to
    the transform's own node's PARENT, never the node itself, and never
    absolute — see `commands._targets.parse_bare_transform_spec`/
    `resolve_node_path`, and `fatass.resolve.cwd.expand`'s own "a run of
    N>=1 dots ascends N-1 levels" rule). `anchor` is that parent's own
    path, or `ROOT` ("@") for a top-level node's parent (the true
    topology root).

    Ascends from `anchor` to the lowest common ancestor of `anchor` and
    `dep_path`, then descends from there — e.g. a dep two levels up and
    one over renders as "...Sibling", not its own absolute
    "@Grandparent.Sibling"; a dep that's `anchor`'s own child (the
    common case — a plain sibling of the transform's node) renders bare,
    no leading dots at all."""
    anchor_parts = [] if anchor == ROOT else anchor.split(".")
    dep_parts = dep_path.split(".")
    k = 0
    while k < len(anchor_parts) and k < len(dep_parts) and anchor_parts[k] == dep_parts[k]:
        k += 1
    ascend = len(anchor_parts) - k
    descend_parts = dep_parts[k:]
    dots = "" if ascend == 0 else "." * (ascend + 1)
    descend = pascal_node_path(".".join(descend_parts)) if descend_parts else ""
    return dots + descend


def _render_transform_sig(t: TransformSigData, anchor: str) -> str:
    """`transformName<params>(deps)` for one `TransformSigData` — each
    bracket independently omitted when empty (matching the standalone
    `PathedNodeSignature.transformName<params>(deps)` grammar's own
    "independently omittable, defaults to empty" rule — see
    `commands._targets`), so a transform with neither renders as its
    bare name and a transform with only deps renders with just `(...)`,
    same as a human would type by hand. Each dep is identified relative
    to `anchor` (the transform's own node's PARENT — see
    `_relative_dep_expr`), matching exactly how "(deps)" is actually
    parsed back in — never as an absolute path, and regardless of the
    caller's own `pathed=`/`pathed_signature()` choice for the rest of
    the signature (that flag only ever affects how a node names
    *itself*, never how a transform's own deps are spelled)."""
    out = t.name
    if t.type_args:
        out += "<" + " ".join(t.type_args) + ">"
    if t.dep_paths:
        out += "(" + ",".join(_relative_dep_expr(p, anchor) for p in t.dep_paths) + ")"
    return out


def signature(node_path: str, config: SignatureConfig = FULL_TYPED_FULL_STRUCTURED) -> str:
    """`render_signature(build_sig_data(node_path), config)` — the usual
    one-shot entry point. Gathers transforms (see
    `build_sig_data`'s `with_transforms`) iff `config.show_transforms`
    — a caller doesn't need to ask for that separately."""
    return render_signature(build_sig_data(node_path, with_transforms=config.show_transforms), config)


def pathed_signature(
    node_path: str, config: SignatureConfig = FULL_TYPED_FULL_STRUCTURED, *, max_depth: int | None = None
) -> str:
    """Same as `signature()`, but every node identified in the output is
    shown by its topology path (`@<path>`) rather than by bare class
    name — see `render_signature`'s `pathed=True`."""
    return render_signature(
        build_sig_data(node_path, max_depth=max_depth, with_transforms=config.show_transforms),
        config,
        pathed=True,
    )


# --- Parsing a "<NodeType args>" suffix, and matching one against an
# already-existing node --------------------------------------------------
#
# The grammar above is this module's OUTPUT format (rendering an existing
# node's shape as text). The same grammar doubles as an INPUT format in two
# places: `fatass create`'s target syntax (naming a not-yet-existing node's
# type — see `fatass.commands._targets.parse_create_target`) and, here, an
# optional trailing assertion on an argument that names a node which must
# ALREADY exist — e.g. "foo.bar<Chain>" only resolves if "foo.bar" is
# actually a Chain. Both input uses share the exact same suffix syntax and
# per-kind argument shape, so the parsing lives in one place (this module,
# the module that also *renders* that shape) rather than being
# reimplemented per input use.

_BASE_CLASS_SUFFIX = re.compile(
    r"<(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\s+(?P<args>[\s\S]+))?>$"
)
"""One suffix grammar, `<NodeType>` (no args at all — `args` group didn't
match) or `<NodeType arg1 arg2 ...>` (`args` is everything after the
required run of whitespace following the type name) — `\\s+`/`[\\s\\S]+`,
not a literal " "/".", so a signature pretty-printed across multiple
lines (e.g. a `touch -p <file>` tree with entries each on their own
indented line) parses the same as one written on a single line; plain
"." doesn't match a newline, which a bare space in the separator or
`.+` for `args` would both have silently broken. There is no separate
comma-parenthesized form — every argument kind (bare field name,
`dim=RxCx...`, a `Dir`'s path, a named/typed param) shares this one
space-separated grammar; see `_parse_type_args`/`_parse_dir_arg` for how
each `args` string is actually parsed once matched here."""


def _parse_one_named_entry(item: str, target: str) -> tuple[str, str, str]:
    """One `argvar:argtype=argval` / `argvar=argval` / `argvar:argtype`
    entry (see `_split_type_suffix`'s own docstring for the full
    five-shape grammar this is one part of) → `(name, type, value)`,
    with the omitted half(s) defaulted (`argtype` → `str`, `argval` →
    `""`). Called by `_parse_type_args` for each space-separated entry
    that isn't a bare identifier or a `dim=...` — see that function for
    how quoting protects a value's own whitespace."""
    if ":" in item:
        name_part, _, rest = item.partition(":")
        if "=" in rest:
            type_part, _, value_part = rest.partition("=")
        else:
            type_part, value_part = rest, None
    else:
        name_part, _, value_part = item.partition("=")
        type_part = None
    name = name_part.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"invalid parameter name {name!r} in {target!r}")
    type_str = type_part.strip() if type_part else "str"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", type_str):
        raise ValueError(f"invalid parameter type {type_str!r} in {target!r}")
    value_str = value_part if value_part is not None else ""
    return name, type_str, value_str


def _tokenize_space_args(raw: str, target: str) -> list[str]:
    """Split `raw` on unquoted whitespace into whole entries. A
    double-quoted region may start mid-entry (e.g. right after
    `argvar:argtype=`, protecting just the value, not the whole entry)
    and its own interior whitespace doesn't split it; `\\"` and `\\\\`
    are the only recognized escapes (a literal quote or backslash
    inside the quoted region), and the quotes/escaping backslashes
    themselves are stripped from the result — e.g. `argvar:argtype="a
    \\"b\\" c"` → one entry, `argvar:argtype=a "b" c`."""
    tokens: list[str] = []
    buf: list[str] = []
    started = False
    in_quotes = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if in_quotes:
            if ch == "\\" and i + 1 < n and raw[i + 1] in ('"', "\\"):
                buf.append(raw[i + 1])
                i += 2
                continue
            if ch == '"':
                in_quotes = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue
        if ch.isspace():
            if started:
                tokens.append("".join(buf))
                buf = []
                started = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            started = True
            i += 1
            continue
        buf.append(ch)
        started = True
        i += 1
    if in_quotes:
        raise ValueError(f"unterminated quoted value in {target!r}")
    if started:
        tokens.append("".join(buf))
    return tokens


def _parse_type_args(raw: str, target: str) -> dict[str, tuple]:
    """The "<NodeType arg1 arg2 ...>" suffix's space-separated args
    (`_tokenize_space_args` — quote a value with `"..."`,
    `\\"`/`\\\\`-escaped, if it needs to contain whitespace itself), one
    unified grammar for every argument kind a non-`Dir` node uses
    (`Dir`'s own single path argument is handled separately — see
    `_parse_dir_arg` — since it's one raw path, not a list of
    independent entries): each entry is either `dim=<int>x<int>x...`
    (`Array`'s `DIM`, "x"-separated, converted to a tuple of `int`), a
    bare identifier (one `fields` entry — `Tuple`/`Array`'s `FIELDS`,
    untyped/unvalued), or a named, typed argument (`argvar:argtype=
    argval` and its two shorter forms — see `_parse_one_named_entry`,
    e.g. `Chat`'s `PROMPT`). Entries may appear in any order, though
    this module's own rendering always puts fields first, then params,
    then dim."""
    kwargs: dict[str, tuple] = {}
    fields: list[str] = []
    params: list[tuple] = []
    for item in _tokenize_space_args(raw, target):
        if item.startswith("dim="):
            dim_raw = item[len("dim="):]
            try:
                kwargs["dim"] = tuple(int(part) for part in dim_raw.split("x"))
            except ValueError:
                raise ValueError(
                    f"invalid dim {dim_raw!r} in {target!r} — expected e.g. "
                    f"'dim=2x2x2'"
                ) from None
            continue
        if ":" in item or "=" in item:
            params.append(_parse_one_named_entry(item, target))
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item):
            raise ValueError(f"invalid field name {item!r} in {target!r}")
        fields.append(item)
    if fields:
        kwargs["fields"] = tuple(fields)
    if params:
        kwargs["params"] = tuple(params)
    return kwargs


def _parse_dir_arg(raw: str, target: str) -> dict[str, str]:
    """The "<Dir ...>" suffix's one argument: a raw filesystem path
    (absolute or relative), taken as a single space-tokenized entry
    (quoted, `"..."`, if it contains whitespace itself — a real path
    routinely does) rather than split/identifier-checked like
    `_parse_type_args`'s other entry kinds."""
    tokens = _tokenize_space_args(raw, target)
    if len(tokens) != 1:
        raise ValueError(
            f"Dir takes exactly one path argument, e.g. 'name<Dir Assets>' "
            f"or 'name<Dir \"some path\">' in {target!r}"
        )
    return {"path": tokens[0]}


def _split_type_suffix(raw: str) -> tuple[str, str | None, dict[str, tuple]]:
    """Split an optional trailing "<NodeType>" or "<NodeType arg1 arg2
    ...>" off `raw`, returning `(raw_without_suffix, type_name,
    class_kwargs)`.

    `type_name` is `None` if no suffix was present at all (nothing to
    assert/create); `class_kwargs` is always a plain dict — `{}` when
    there's nothing further to check (a bare "<Type>", or one with no
    args), never `None`. See `_BASE_CLASS_SUFFIX` for the suffix grammar
    itself, `_parse_type_args`/`_parse_dir_arg` for what the args parse
    into (`Dir` gets its own single-path parsing; every other kind
    shares `_parse_type_args`)."""
    match = _BASE_CLASS_SUFFIX.search(raw)
    if not match:
        return raw, None, {}
    stripped, type_name, args = raw[: match.start()], match.group("name"), match.group("args")
    if args is None:
        return stripped, type_name, {}
    kwargs = _parse_dir_arg(args, raw) if type_name == "Dir" else _parse_type_args(args, raw)
    return stripped, type_name, kwargs


def validate_node_signature(node_path: str, type_name: str, expected: dict[str, tuple], raw: str) -> None:
    """Raise `TopologyValidationError` unless the already-resolved,
    already-existing node at `node_path` matches `type_name` (its
    `Node._base_kind()` name) and, for whichever of FIELDS/DIM/PATH/
    named params `expected` (from `_split_type_suffix`, already parsed)
    itself specifies, that those match too — an empty `expected` (a bare
    "<Type>", or one with empty/no args) only asserts the kind, nothing
    more. `raw` is the original, unstripped argument text (e.g.
    "foo.bar<Chain>"), used only to phrase the error."""
    node_cls = _import_node(node_path)
    actual_kind = node_cls._base_kind().__name__
    if actual_kind != type_name:
        raise TopologyValidationError(
            f"{pathed_signature(node_path, SIMPLE_TYPED, max_depth=0)} doesn't "
            f"match the expected type {type_name!r} in {raw!r}"
        )
    if "fields" in expected:
        actual_fields = tuple(getattr(node_cls, "FIELDS", ()))
        if actual_fields != expected["fields"]:
            raise TopologyValidationError(
                f"{node_path} has FIELDS {actual_fields!r}, expected "
                f"{expected['fields']!r} in {raw!r}"
            )
    if "dim" in expected:
        actual_dim = tuple(getattr(node_cls, "DIM", ()))
        if actual_dim != expected["dim"]:
            raise TopologyValidationError(
                f"{node_path} has DIM {actual_dim!r}, expected {expected['dim']!r} in {raw!r}"
            )
    if "params" in expected:
        # `inspect.get_annotations` (not `node_cls.__dict__.get(
        # "__annotations__", {})`) — see `Node._type_args()`'s own
        # docstring for why the dict-lookup form doesn't work under
        # PEP 649 deferred annotations (the default since Python 3.14).
        node_annotations = inspect.get_annotations(node_cls)
        for name, type_str, value_str in expected["params"]:
            attr_name = name.upper()
            if attr_name not in node_annotations:
                raise TopologyValidationError(
                    f"{node_path} has no declared parameter {name!r} in {raw!r}"
                )
            actual_type = node_annotations[attr_name]
            actual_type_name = (
                actual_type if isinstance(actual_type, str) else getattr(actual_type, "__name__", str(actual_type))
            )
            if actual_type_name != type_str:
                raise TopologyValidationError(
                    f"{node_path} has parameter {name!r} typed {actual_type_name!r}, "
                    f"expected {type_str!r} in {raw!r}"
                )
            actual_value = node_cls.__dict__.get(attr_name, "")
            if str(actual_value) != value_str:
                raise TopologyValidationError(
                    f"{node_path} has parameter {name!r} = {actual_value!r}, "
                    f"expected {value_str!r} in {raw!r}"
                )
    if "path" in expected:
        actual_path = getattr(node_cls, "PATH", "")
        if actual_path != expected["path"]:
            raise TopologyValidationError(
                f"{node_path} has PATH {actual_path!r}, expected {expected['path']!r} in {raw!r}"
            )


# --- Shared bracket-splitting primitives ------------------------------------
#
# Three small scanners, each used by more than one caller across `touch`'s
# multi-statement/children-block grammar and `_targets`'s new
# `PathedNodeSignature.transformName<params>(deps)` transform-target
# grammar — kept here (not duplicated in `commands/touch.py`/
# `commands/_targets.py`) since both of those already depend on this
# module, but neither can depend on the other without a cycle.


def _split_trailing_parens(raw: str) -> tuple[str, str | None]:
    """Split a trailing "(...)" off `raw` into (raw_without_it,
    inner_content), or (raw, None) if `raw` doesn't end in one at all.

    A parenthesis only ever starts/ends this trailing group when it
    appears outside any "<...>" or "{...}" — an angle-bracketed span (a
    node's own `<NodeType arg1 arg2>` suffix, or the transform-target
    grammar's `<params>`) may itself contain a literal "(" (an unquoted
    param value can, e.g. "x=(1)"), and a curly-braced transforms block
    (see `_split_trailing_curly`) always does (each entry's own
    "(deps)") — neither is mistaken for this group's own start; tracking
    separate angle- and curly-bracket depths is what makes that
    distinction possible. Also respects "..."-quoted regions (so a
    literal "<"/">"/"{"/"}"/"("/")" inside a quoted value doesn't confuse
    any depth) — finds the outermost, non-nested "(" matching the final
    ")", not just the first "(" anywhere in the string.

    Used for `touch`'s own node-tree "(Child1<Type1>(...),Child2<Type2>)"
    children block, and for peeling the transform-target grammar's own
    trailing "(deps)" group."""
    raw = raw.strip()
    if not raw.endswith(")"):
        return raw, None
    paren_depth = 0
    angle_depth = 0
    curly_depth = 0
    start = None
    in_quotes = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if in_quotes:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
        elif ch == "<":
            angle_depth += 1
        elif ch == ">":
            angle_depth -= 1
        elif ch == "{":
            curly_depth += 1
        elif ch == "}":
            curly_depth -= 1
        elif ch == "(" and angle_depth == 0 and curly_depth == 0:
            if paren_depth == 0:
                start = i
            paren_depth += 1
        elif ch == ")" and angle_depth == 0 and curly_depth == 0:
            paren_depth -= 1
            if paren_depth == 0:
                if i != n - 1:
                    raise ValueError(f"text after closing ')' in {raw!r}")
                return raw[:start].strip(), raw[start + 1 : i]
        i += 1
    raise ValueError(f"unbalanced '(...)' in {raw!r}")


def _split_trailing_angle(raw: str) -> tuple[str, str | None]:
    """Split a trailing "<...>" off `raw` into (raw_without_it,
    inner_content), or (raw, None) if `raw` doesn't end in one at all —
    respecting "..."-quoted regions, so a literal ">" inside a quoted
    value doesn't end it early. Unlike `_split_type_suffix`'s
    similarly-shaped suffix, there's no leading type name expected
    here — just the bracket's raw content — used for the transform-
    target grammar's own trailing "<params>" group (peeled from what's
    left after `_split_trailing_parens` has already removed any
    "(deps)")."""
    raw = raw.strip()
    if not raw.endswith(">"):
        return raw, None
    depth = 0
    start = None
    in_quotes = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if in_quotes:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
        elif ch == "<":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                if i != n - 1:
                    raise ValueError(f"text after closing '>' in {raw!r}")
                return raw[:start].strip(), raw[start + 1 : i]
        i += 1
    raise ValueError(f"unbalanced '<...>' in {raw!r}")


def _split_trailing_curly(raw: str) -> tuple[str, str | None]:
    """Split a trailing "{...}" off `raw` into (raw_without_it,
    inner_content), or (raw, None) if `raw` doesn't end in one at all —
    same "..."-quoted-region handling as `_split_trailing_parens`/
    `_split_trailing_angle`, but tracking only curly-brace depth itself
    (a transform entry's own "<params>"/"(deps)" groups inside never
    contain a literal "{"/"}", so there's no sibling bracket to shield
    against the way `_split_trailing_parens` has to shield "(" from
    "<...>"). Used for a node's own optional transforms block in the
    full signature grammar (see `FULL_SIGNATURE`):
    "NodeClassName<NodeType>{transform1<params>(deps);...}(children)" —
    peeled AFTER the trailing "(...)" children block (see
    `_split_trailing_parens`, which itself already knows to skip over an
    unpeeled "{...}" block's own parens) and BEFORE the "<...>" type
    suffix (see `_split_type_suffix`), since it sits textually between
    the two."""
    raw = raw.strip()
    if not raw.endswith("}"):
        return raw, None
    depth = 0
    start = None
    in_quotes = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if in_quotes:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                if i != n - 1:
                    raise ValueError(f"text after closing '}}' in {raw!r}")
                return raw[:start].strip(), raw[start + 1 : i]
        i += 1
    raise ValueError(f"unbalanced '{{...}}' in {raw!r}")


def _split_top_level(raw: str, sep: str) -> list[str]:
    """Split `raw` on `sep` characters that aren't nested inside
    "(...)"/"<...>"/"{...}" or a "..."-quoted region — one entry per
    item (each of which may itself contain any of those, recursively).
    A single combined depth (not tracked separately per bracket kind) is
    enough here — unlike `_split_trailing_parens`, this only needs to
    know "is this separator nested at all", never which specific bracket
    it's nested inside. Shared by `_split_top_level_commas` (`sep=","`)
    and `_split_top_level_semicolons` (`sep=";"`) — the two differ only
    in which character ends an entry."""
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
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _split_top_level_commas(raw: str) -> list[str]:
    """`_split_top_level(raw, ",")` — used for `touch`'s own node-tree
    children block, and for the transform-target grammar's own "(deps)"
    and "<params>" groups."""
    return _split_top_level(raw, ",")


def _split_top_level_semicolons(raw: str) -> list[str]:
    """`_split_top_level(raw, ";")` — used for a node's own "{...}"
    transforms block (see `FULL_SIGNATURE`/`commands.touch`): each
    "transformName<params>(deps)" entry is ";"-terminated, a statement-
    list convention deliberately unlike the comma-separated `(...)`/
    "<...>" groups elsewhere. A trailing ";" (including after the very
    last entry, which `_render_transform_sig`'s own output always has)
    just leaves one harmless, filtered-out empty trailing part."""
    return _split_top_level(raw, ";")
