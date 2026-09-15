import inspect
from pathlib import Path

from .._internal.paths import HOME_ROOT

_TOPOLOGY_PREFIX = "fatass.topology."
_NODE_PREFIX = "fatass.node."


def _quote_param_value_if_needed(value: str) -> str:
    """A named-param's value (see `Node._type_args()`), quoted (double
    quotes, `\\"`/`\\\\` escaped — the same convention
    `fatass.signature._tokenize_space_args` parses back) if and only if
    it contains whitespace — the space-separated `<NodeType name:type=
    value ...>` suffix form splits entries on unquoted whitespace, so an
    unquoted value containing any would otherwise be silently split into
    several bogus entries on a later re-parse of this same rendered
    text. Left bare otherwise (an empty value, or one with no
    whitespace, is already unambiguous either way, and stays exactly as
    typed rather than growing needless quotes)."""
    if not any(ch.isspace() for ch in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class NodeMeta(type):
    """A `Node` subclass is almost always referred to as a class object
    itself (`Education.length()`, `Info.write(...)`), never instantiated
    (`Chain` is the one exception) — so a plain instance `__repr__` would
    never actually be seen. Overriding `__repr__` here, on the metaclass,
    is what makes `repr(SomeNodeClass)` itself show something useful
    (`fatass ls` and any debugging print of a node class) instead of
    Python's default `<class 'module.Name'>`.

    Shows the fatass framework kind the class is built on — its nearest
    `fatass.node.*`-defined ancestor in `__mro__` (most-specific first,
    so a typed variant like `SingleCsv`/`ArrayCsv` is picked over the
    plain `Single`/`Array` it's built on, and a bare `Node` subclass
    falls all the way back to `Node` itself) — plus that kind's own
    configuration: `DIM` (`Array`/its typed variants) and/or `FIELDS`
    (`Tuple`, `SingleCsv`, `ArrayCsv`), whichever the kind actually
    defines non-empty."""

    def __repr__(cls) -> str:
        kind = cls._base_kind()
        return f"{kind.__name__}({','.join(cls._type_args())})"

    def __getattr__(cls, name: str):
        """Lets a *second* (or third, ...) named-schema-child hop off an
        already-indexed `Chain`/`Dictionary`-item-derived class keep
        resolving, instead of only ever working for the first hop.

        `Chain`'s own indexing (`some_chain_instance[i]`, or
        `Dictionary`'s `some_dict_instance[key]`) returns a `_ChainItem`/
        `_DictItem` *instance* (see node/chain.py, node/dictionary.py),
        whose own `__getattr__` (an ordinary instance method) is what
        makes `chain_instance[i].some_child` work at all — it dynamically
        builds a subclass of `some_child`'s real class, with
        `_assets_dir()` overridden to that index's own directory. But
        that result is a plain *class*, not another `_ChainItem` — and
        `getattr(SomeClass, name)`, when `SomeClass` itself doesn't
        define `name`, falls through to the *metaclass's* `__getattr__`
        (this one), never back to `_ChainItem`'s. Without this method,
        `chain_instance[i].some_child` works but
        `chain_instance[i].some_child.grandchild` doesn't — a plain
        `AttributeError`, since the returned class has no schema-child
        resolution of its own past that first hop.

        Mirrors `_ChainItem.__getattr__`/`_DictItem.__getattr__`'s own
        logic (see either method's docstring for the full reasoning
        behind each overridden classmethod) — kept in sync by hand
        rather than sharing one helper, since those run as instance
        methods on `_ChainItem`/`_DictItem` and this one as a
        classmethod-equivalent on the metaclass; they build the same
        shape of result from different starting data. `_index_key`/
        `_index_owner_cls` are the shared, kind-agnostic names both
        `Chain` and `Dictionary` items stamp (an int position or a
        string key; the `Chain`/`Dictionary` subclass itself) — this
        method, and `core.transform._resolve_dependency`'s own
        `_sibling` lookup, work identically for either kind without
        needing to know which one they're looking at.

        Only fires for a class that's itself already index-scoped
        (carries `_sibling`, stamped exclusively by this same mechanism
        — never present on an ordinary, non-indexed `Node` subclass) —
        an ordinary class hitting an unknown attribute still gets a
        plain `AttributeError`, same as always. Checking `name`'s
        leading "_" first (before even doing that `hasattr` check, which
        itself calls `getattr` and would otherwise recurse back into
        this same method) keeps a merely-missing dunder/private
        attribute (on ANY class, indexed or not) from ever reaching the
        schema-child-resolution logic below, or looping."""
        if name.startswith("_") or not hasattr(cls, "_sibling"):
            raise AttributeError(name)

        from ..core.transform import _import_node  # local: avoid a cycle
        from ..errors import TopologyValidationError

        full_path = f"{cls._topology_path()}.{name}"
        try:
            schema_cls = _import_node(full_path)
        except TopologyValidationError:
            # `name` isn't a real schema child at all — a clean, ordinary
            # AttributeError (not TopologyValidationError) so a caller
            # doing `getattr(cls, name, default)`/`hasattr(cls, name)` to
            # probe for some *other* kind of attribute (e.g. `FIELDS`,
            # `DIM`, `PATH` — see `_type_args()`) gets its default back
            # instead of an unrelated crash.
            raise AttributeError(name) from None

        index_key = cls._index_key()
        index_owner_cls = cls._index_owner_cls()
        # A home/-tree bookkeeping slot for THIS specific hop, distinct
        # per full lineage of indices that led here (not just this one
        # hop's own index) — `cls._index_home_dir()` is itself already
        # that same kind of slot for the parent, so nesting `name` under
        # it naturally accumulates the whole path of indices. Always
        # home/-based, regardless of what `cls._assets_dir()` actually
        # resolves to (which, for a `Dir`-derived `cls`, is some real
        # external directory) — this is bookkeeping space, never to be
        # confused with a node's own real content, and must never touch
        # a `Dir`'s externally-managed real directory.
        index_home_dir = cls._index_home_dir() / name
        is_new = not index_home_dir.is_dir()
        index_home_dir.mkdir(parents=True, exist_ok=True)
        namespace = {
            "_topology_path": classmethod(lambda c, _p=full_path: _p),
            "_index_key": classmethod(lambda c, _i=index_key: _i),
            "_index_owner_cls": classmethod(lambda c, _lc=index_owner_cls: _lc),
            "_sibling": classmethod(
                lambda c, sib_name: getattr(c._index_owner_cls()()[c._index_key()], sib_name)
            ),
            "_index_home_dir": classmethod(lambda c, _d=index_home_dir: _d),
            # The actual, already-correctly-indexed object `name` was
            # resolved off of — not just this hop's *schema* (index-
            # independent, same value at every index by the topological
            # invariant), but the real parent instance/class a subclass
            # with its own `_assets_dir()` override (e.g. `Dir`) needs to
            # walk up through to resolve correctly per index instead of
            # silently re-resolving against the bare, unindexed schema
            # class (which would collapse every index to the same
            # answer). See `Dir._resolved_path()`.
            "_parent_indexed": cls,
        }
        # A schema child with its OWN `_assets_dir()` override (`Dir`,
        # resolving to a real external filesystem path, not `home/`) must
        # not have that shadowed by the generic home/-relative override
        # below — doing so would silently replace its real resolution
        # logic with a bogus phantom `home/` directory that gets created
        # and used instead, and never actually invoke `Dir`'s own
        # `_resolved_path()` at all. It still gets `_index_home_dir`
        # (above) as its own per-index bookkeeping slot — that's where a
        # `Dir` looks for its optional per-index `.path` override file
        # (see `Dir._effective_path()`), letting a chain-indexed `Dir`'s
        # real directory actually differ per index despite its `PATH`
        # class attribute being schema-fixed.
        has_custom_assets_dir = schema_cls._assets_dir.__func__ is not Node._assets_dir.__func__
        if has_custom_assets_dir:
            indexed_cls = type(f"{schema_cls.__name__}@{index_key}", (schema_cls,), namespace)
        else:
            namespace["_assets_dir"] = classmethod(lambda c, _dir=index_home_dir: _dir)
            indexed_cls = type(f"{schema_cls.__name__}@{index_key}", (schema_cls,), namespace)
        if is_new:
            indexed_cls.on_created()
        return indexed_cls


class Node(metaclass=NodeMeta):
    """Base class for a node's definition.

    Subclassed once per `fatass/topology/.../<name>/<name>.py`. Carries no
    per-instance state — all path resolution is derived from where the
    subclass is defined (`cls.__module__`).
    """

    @classmethod
    def _topology_path(cls) -> str:
        module = cls.__module__
        if not module.startswith(_TOPOLOGY_PREFIX):
            raise ValueError(
                f"{cls!r} is not defined under fatass.topology "
                f"(module is {module!r})"
            )
        path = module[len(_TOPOLOGY_PREFIX):]
        # A Node subclass is defined inside its own <name>.py, so
        # cls.__module__ is always "...<name>.<name>" — one trailing segment
        # (the node's own file, always named after its own directory) more
        # than the node's actual topology path. Strip it unconditionally.
        return path.rsplit(".", 1)[0]

    @classmethod
    def _assets_dir(cls) -> Path:
        relative = cls._topology_path().replace(".", "/")
        return HOME_ROOT / relative

    @classmethod
    def _base_kind(cls) -> type["Node"]:
        """The fatass framework kind this class is built on — its nearest
        `fatass.node.*`-defined ancestor in `__mro__` (most-specific
        first, so a typed variant like `SingleCsv`/`ArrayCsv` is picked
        over the plain `Single`/`Array` it's built on, and a bare `Node`
        subclass falls all the way back to `Node` itself). The single
        canonical implementation of this MRO walk — `NodeMeta.__repr__`,
        `fatass.ls`, and `fatass.signature` all call this rather than
        each re-walking `__mro__` themselves."""
        for base in cls.__mro__:
            if base.__module__.startswith(_NODE_PREFIX):
                return base
        return cls

    @classmethod
    def _type_args(cls) -> list[str]:
        """This class's fatass-base-kind constructor-like arguments, in
        the canonical order/shape `fatass create`'s own target grammar
        and `fatass.signature` both use — one space-separated `<NodeType
        arg1 arg2 ...>` suffix, every argument kind sharing that same
        grammar (no more separate comma-parenthesized form): a `Tuple`/
        `Array`'s `FIELDS`, each as its own bare-identifier argument,
        then any named, typed class attributes this exact class declares
        (see below) as their own `name:type=value` arguments, then an
        `Array`'s `DIM` as a `dim=RxCx...` argument, then a `Dir`'s
        `PATH` as its own argument (quoted — see
        `_quote_param_value_if_needed` — since a real filesystem path may
        contain whitespace, which the space-separated suffix would
        otherwise split on). Empty for a kind with no such arguments
        (`Chain`, `Single`, plain `Node`).

        A named, typed argument (e.g. `Chat`'s `PROMPT`) is discovered
        generically, via `inspect.get_annotations(cls)` — deliberately
        that, not plain `cls.__annotations__` (which follows the MRO
        like any other attribute lookup, and — under PEP 649 deferred
        evaluation, the default since Python 3.14 — isn't even a plain
        `cls.__dict__` entry to begin with, so `cls.__dict__.get(...)`
        can't be used as an inheritance-avoiding substitute either):
        a scaffolded node only ever gets its own annotated assignment
        baked into its own class body when `create`'s target actually
        gave it one (see `scaffold._class_body`) — if it didn't, this
        must render nothing for that argument at all (the same "an
        omitted piece is simply not printed" rule every other argument
        already follows), not silently inherit and re-print the base
        kind's own default from `Chat` itself — and `inspect.get_
        annotations` is exactly the modern, PEP-649-safe way to get a
        class's own annotations without following its MRO. `FIELDS`/
        `DIM`/`PATH` are excluded from this generic pass since they're
        handled above, by name, already — and, as scaffolded, are never
        themselves annotated assignments (see `scaffold._class_body`'s
        own plain, unannotated `NAME = value` lines for them), so in
        practice they'd never collide with this pass regardless."""
        args: list[str] = []
        fields = getattr(cls, "FIELDS", ())
        if fields:
            args.extend(fields)
        own_annotations = inspect.get_annotations(cls)
        for attr_name, attr_type in own_annotations.items():
            if attr_name in ("FIELDS", "DIM", "PATH"):
                continue
            type_name = attr_type if isinstance(attr_type, str) else getattr(
                attr_type, "__name__", str(attr_type)
            )
            value = _quote_param_value_if_needed(str(cls.__dict__.get(attr_name, "")))
            args.append(f"{attr_name.lower()}:{type_name}={value}")
        dim = getattr(cls, "DIM", ())
        if dim:
            args.append("dim=" + "x".join(str(d) for d in dim))
        path = getattr(cls, "PATH", "")
        if path:
            args.append(_quote_param_value_if_needed(path))
        return args

    @classmethod
    def modify_sys_prompt(cls) -> str | None:
        """Extra `--append-system-prompt` guidance for `fatass modify`
        when editing a node file that subclasses this class — appended
        after the static conventions/command prompts. None by default;
        override in a subclass (see Chain) to teach the agent
        conventions specific to that kind of node."""
        return None

    @classmethod
    def on_created(cls) -> None:
        """Called once, right after `fatass create` scaffolds a new node
        of this class and the topology tree is reloaded so the class is
        actually importable — a chance for a subclass with content of its
        own beyond a bare directory (see Single, Array) to materialize it
        immediately instead of waiting for first access. No-op by default:
        an ordinary Node has nothing to create beyond the empty home/
        directory `create_node()` already made."""
        return None

    @classmethod
    def purge_self(cls) -> int | None:
        """Override to replace `fatass purge`'s default behavior (delete
        every entry directly under this node's own home/ directory) with
        something else — e.g. clearing fixed-name file(s) in place instead
        of removing them (see Single, Array). Returns the number of
        entries purged, or None (the default) to mean "no override, use
        the generic delete-everything behavior"."""
        return None

    @classmethod
    def on_child_moved(cls, old_child_stem: str, new_child_stem: str) -> None:
        """Called on a node's own class, after `fatass move` renames one of
        its *direct* children in place (same parent, only the leaf segment
        changed) — a chance for a node class with its own extra structure
        mirroring its children's names (see `Chain`) to keep that mirror
        in sync. No-op by default: an ordinary `Node` has no such mirror,
        so `move_node`'s own generic topology/home/ directory move (already
        done by the time this is called) is the whole story. `move_node`
        calls this on the child's *parent's* class, unaware of what (if
        anything) that class actually needs to do about it."""
        return None
