import ast

from ..errors import TopologyValidationError
from .scaffold import _node_dir

_TOPOLOGY_IMPORT_PREFIX = "fatass.topology."


def _param_name(node_path: str) -> str:
    """The last dotted segment, unchanged — node names are already
    snake_case directory names, and this is the conventional parameter
    name for a dependency on that node (e.g. "hunt.shortlist" -> "shortlist")."""
    return node_path.rsplit(".", 1)[-1]


def _alias(node_path: str) -> str:
    """PascalCase form of the parameter name — the conventional import
    alias (e.g. "writing_sample" -> "WritingSample"), matching
    fatass/prompts/conventions.md."""
    return "".join(word.capitalize() for word in _param_name(node_path).split("_"))


def _transform_file(node_path: str, transform_name: str):
    file_path = _node_dir(node_path) / f"{transform_name}.py"
    if not file_path.is_file():
        raise TopologyValidationError(
            f"no transform named {transform_name!r} under {node_path!r}"
        )
    return file_path


def _parse_transform(node_path: str, transform_name: str):
    file_path = _transform_file(node_path, transform_name)
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(
        (
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == transform_name
        ),
        None,
    )
    if func is None:
        raise TopologyValidationError(
            f"{file_path} does not define a function named {transform_name!r}"
        )
    return file_path, source, tree, func


def _existing_imports(tree: ast.Module) -> dict[str, str]:
    """{alias: dep_node_path} for every top-level `from
    fatass.topology.<path> import <RealClassName> as <alias>` statement.
    The imported name varies per dependency (it's that dependency's own
    real class name, not a fixed "Node"), so any name imported from a
    `fatass.topology.<path>` module counts."""
    imports = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith(_TOPOLOGY_IMPORT_PREFIX):
            continue
        dep_path = node.module[len(_TOPOLOGY_IMPORT_PREFIX) :]
        for alias in node.names:
            imports[alias.asname or alias.name] = dep_path
    return imports


def _existing_deps(func: ast.FunctionDef, imports: dict[str, str]) -> dict[str, str]:
    """{param_name: dep_node_path} for every existing Node-typed
    parameter, matched against `imports`."""
    deps = {}
    for arg in func.args.args:
        if isinstance(arg.annotation, ast.Name) and arg.annotation.id in imports:
            deps[arg.arg] = imports[arg.annotation.id]
    return deps


def _matching_paren(source: str, open_pos: int) -> int:
    """Index of the `)` matching the `(` at `open_pos`, found by depth
    counting rather than a naive first-`)` search — a parameter default
    containing its own call (e.g. `= foo()`) would otherwise be mistaken
    for the signature's actual closing paren."""
    depth = 0
    for i in range(open_pos, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"no matching ')' for '(' at position {open_pos}")


def _signature_paren_positions(source: str, func: ast.FunctionDef) -> tuple[int, int]:
    """(open_paren_index, close_paren_index) for `func`'s parameter list —
    raises if the signature spans more than one line, which bind/unbind
    don't support (every transform in this topology's convention is a
    single-line signature; this turns the unsupported case into a clear
    error instead of silently splicing the wrong text)."""
    line_start = 0
    for _ in range(func.lineno - 1):
        line_start = source.index("\n", line_start) + 1
    open_pos = source.index("(", line_start)
    close_pos = _matching_paren(source, open_pos)
    if "\n" in source[open_pos:close_pos]:
        raise TopologyValidationError(
            f"{func.name}'s signature spans multiple lines — bind/unbind "
            f"only support a single-line signature"
        )
    return open_pos, close_pos


def _new_param_insertion(source: str, func: ast.FunctionDef) -> tuple[int, bool, bool]:
    """(insert_pos, needs_leading_comma, needs_trailing_comma) for adding
    new non-default `Node`-typed parameters to `func`. Python requires
    every parameter without a default to come before every parameter that
    has one, so new params are inserted right before the first existing
    defaulted parameter (or before the closing paren if none exist), not
    always appended at the end."""
    open_pos, close_pos = _signature_paren_positions(source, func)
    args = func.args.args
    n_defaults = len(func.args.defaults)
    first_default_idx = len(args) - n_defaults if n_defaults else len(args)

    if first_default_idx >= len(args):
        insert_pos = close_pos
        needs_leading = source[open_pos + 1 : close_pos].strip() != ""
        needs_trailing = False
    else:
        # Inserting right before an existing (defaulted) parameter: if
        # anything precedes it, the source already has the mandatory
        # ", " separator right there (valid Python requires it) — so no
        # leading comma of our own is needed either way. Something
        # (the anchor itself) always follows, so a trailing one is.
        anchor = args[first_default_idx]
        line_start = 0
        for _ in range(anchor.lineno - 1):
            line_start = source.index("\n", line_start) + 1
        insert_pos = line_start + anchor.col_offset
        needs_leading = False
        needs_trailing = True

    return insert_pos, needs_leading, needs_trailing


def _last_import_end(source: str, tree: ast.Module) -> int:
    """Byte offset right after the last top-level import statement (or 0
    if there are none — shouldn't happen given every transform file
    starts with `import fatass`)."""
    import_nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not import_nodes:
        return 0
    last = max(import_nodes, key=lambda n: n.end_lineno)
    pos = 0
    for _ in range(last.end_lineno):
        pos = source.index("\n", pos) + 1
    return pos


def bound_dep_paths(node_path: str, transform_name: str) -> list[str]:
    """Node paths currently bound as declared `Node`-typed parameters on
    `transform_name` — used by `bind -a` to clear every existing binding
    before applying the new set."""
    _file_path, _source, tree, func = _parse_transform(node_path, transform_name)
    imports = _existing_imports(tree)
    return list(_existing_deps(func, imports).values())


def bind_transform(node_path: str, transform_name: str, dep_node_paths: list[str]) -> list[str]:
    """Add each of `dep_node_paths` as a declared `Node`-typed parameter
    (and matching import) on `transform_name`'s function — the
    deterministic alternative to `modify --prompt "add a dependency on
    X"`. Doesn't call free(), and never touches a `fatass.free(...)`
    call's `readable=[...]` or prompt text — wiring the new parameter
    into a specific call is left to a human or a follow-up `modify`.

    Returns the subset of `dep_node_paths` actually newly bound (already-
    bound ones are silently skipped, idempotent)."""
    file_path, source, tree, func = _parse_transform(node_path, transform_name)
    imports = _existing_imports(tree)
    deps = _existing_deps(func, imports)
    bound_paths = set(deps.values())

    to_bind = [p for p in dep_node_paths if p not in bound_paths]

    seen_params = dict(deps)  # param_name -> dep_path, extended as we validate
    new_params: list[tuple[str, str, str]] = []  # (param_name, alias, dep_path)
    for dep_path in to_bind:
        param_name = _param_name(dep_path)
        alias = _alias(dep_path)
        existing = seen_params.get(param_name)
        if existing is not None and existing != dep_path:
            raise TopologyValidationError(
                f"can't bind {dep_path!r}: parameter name {param_name!r} is "
                f"already used for {existing!r}"
            )
        seen_params[param_name] = dep_path
        new_params.append((param_name, alias, dep_path))

    if not new_params:
        return []

    insert_pos, needs_leading, needs_trailing = _new_param_insertion(source, func)
    joined = ", ".join(f"{name}: {alias}" for name, alias, _dep in new_params)
    param_text = (", " if needs_leading else "") + joined + (", " if needs_trailing else "")
    new_source = source[:insert_pos] + param_text + source[insert_pos:]

    import_insert_pos = _last_import_end(source, tree)
    import_lines = "".join(
        f"from fatass.topology.{dep_path} import {alias} as {alias}\n"
        for _name, alias, dep_path in new_params
        if alias not in imports
    )
    if import_lines:
        new_source = new_source[:import_insert_pos] + import_lines + new_source[import_insert_pos:]

    file_path.write_text(new_source, encoding="utf-8")
    return [dep_path for _name, _alias, dep_path in new_params]


def unbind_transform(node_path: str, transform_name: str, dep_node_paths: list[str]) -> list[str]:
    """Remove each of `dep_node_paths` from `transform_name`'s declared
    parameters (and its import, if no longer referenced anywhere else in
    the file). Refuses — mirroring `remove_node`'s "still depended on"
    check, at the parameter level — if the parameter is still referenced
    anywhere in the function body (e.g. still sitting in a
    `readable=[...]` list); remove that reference first.

    Returns the subset of `dep_node_paths` actually unbound."""
    file_path, source, tree, func = _parse_transform(node_path, transform_name)
    imports = _existing_imports(tree)
    deps = _existing_deps(func, imports)
    dep_to_param = {dep: param for param, dep in deps.items()}

    to_unbind = []
    for dep_path in dep_node_paths:
        param_name = dep_to_param.get(dep_path)
        if param_name is None:
            raise TopologyValidationError(
                f"{dep_path!r} is not currently bound to "
                f"{transform_name}@{node_path}"
            )
        used = any(
            isinstance(n, ast.Name) and n.id == param_name
            for stmt in func.body
            for n in ast.walk(stmt)
        )
        if used:
            raise TopologyValidationError(
                f"can't unbind {dep_path!r}: parameter {param_name!r} is "
                f"still referenced in {transform_name}'s body — remove "
                f"that reference first"
            )
        to_unbind.append((param_name, dep_path))

    if not to_unbind:
        return []

    unbind_params = {param for param, _dep in to_unbind}
    remaining_args = [a for a in func.args.args if a.arg not in unbind_params]
    # every arg not being removed, plus every arg being removed, sorted by
    # source position descending so earlier splices don't invalidate later
    # (here: later-in-file) offsets
    removed_args = sorted(
        (a for a in func.args.args if a.arg in unbind_params),
        key=lambda a: a.col_offset,
        reverse=True,
    )

    new_source = source
    all_args = func.args.args
    for arg in removed_args:
        idx = all_args.index(arg)
        start = arg.col_offset
        end = arg.end_col_offset
        if idx + 1 < len(all_args):
            # remove the trailing ", " up to the next arg's start
            end = all_args[idx + 1].col_offset
        elif idx > 0:
            # last arg being removed: remove the leading ", " from the
            # previous (kept) arg's end
            start = all_args[idx - 1].end_col_offset
        line_start = 0
        for _ in range(arg.lineno - 1):
            line_start = source.index("\n", line_start) + 1
        abs_start = line_start + start
        abs_end = line_start + end
        new_source = new_source[:abs_start] + new_source[abs_end:]

    # Drop now-unused imports: an alias still used by a remaining param,
    # or still referenced anywhere else in the file, is kept.
    remaining_param_aliases = {
        a.annotation.id for a in remaining_args if isinstance(a.annotation, ast.Name)
    }
    referenced_names = {n.id for n in ast.walk(ast.parse(new_source)) if isinstance(n, ast.Name)}

    unbound_dep_paths = {dep for _param, dep in to_unbind}
    imports_to_drop = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith(_TOPOLOGY_IMPORT_PREFIX):
            continue
        dep_path = node.module[len(_TOPOLOGY_IMPORT_PREFIX) :]
        if dep_path not in unbound_dep_paths:
            continue
        alias = node.names[0].asname or node.names[0].name
        if alias in remaining_param_aliases or alias in referenced_names:
            continue
        imports_to_drop.append(node)

    # Remove whole import lines bottom-to-top: each line's offset is
    # located against the original `source`, so an earlier (smaller
    # lineno) removal must happen after later ones, or its own line
    # number would already be stale.
    for node in sorted(imports_to_drop, key=lambda n: n.lineno, reverse=True):
        line_start = 0
        for _ in range(node.lineno - 1):
            line_start = source.index("\n", line_start) + 1
        line_end = source.index("\n", line_start) + 1
        new_source = new_source[:line_start] + new_source[line_end:]

    file_path.write_text(new_source, encoding="utf-8")
    return [dep_path for _param, dep_path in to_unbind]
