import importlib
import pkgutil
import sys


def reload_all(package_name: str) -> None:
    """Evict `package_name` and every already-imported submodule of it from
    sys.modules, then re-walk the current on-disk tree via import_all.

    Within one interpreter (notably the `shell` REPL, where multiple
    commands run in the same process) a topology-mutating command
    (create/modify/move/remove/archive/retrieve) changes files on disk but
    not the module objects already cached in sys.modules from the initial
    `import fatass` — a later command would otherwise see stale entries:
    a moved/removed node still importable under its old path, or a
    modified transform still running its pre-edit code. Re-running after
    such a command clears that staleness."""
    prefix = f"{package_name}."
    for name in [n for n in sys.modules if n == package_name or n.startswith(prefix)]:
        del sys.modules[name]
    import_all(package_name)


def import_all(package_name: str) -> None:
    """Recursively import every submodule of `package_name`, so the whole
    tree becomes attribute-accessible (`fatass.topology.node1.node2`,
    `...transforms.synthesize`) right after `import fatass`, instead of
    needing an explicit import per node or transform. Recurses into
    packages (dirs with __init__.py); plain modules (a node's node.py, a
    transform file) are imported but not recursed into.

    Safe to do eagerly: importing a transform file only defines its
    function(s) — it doesn't call fatass.free(), which only happens if the
    function itself is invoked. Same convention as node.py already relies
    on: module-level code in the topology tree must stay side-effect-free.
    """
    package = importlib.import_module(package_name)
    for info in pkgutil.iter_modules(package.__path__):
        child_name = f"{package_name}.{info.name}"
        if info.ispkg:
            import_all(child_name)
        else:
            importlib.import_module(child_name)


def import_transforms(package_name: str) -> None:
    """For a node's `transforms/` package: import every transform file and
    re-export its function under the file's own name, so e.g.
    `fatass.topology.node3.transforms.synthesize` is directly the
    function — mirroring how a node's own __init__.py re-exports `Node`
    from node.py, rather than leaving it at `...transforms.synthesize.synthesize`.
    """
    package = importlib.import_module(package_name)
    for info in pkgutil.iter_modules(package.__path__):
        if info.ispkg:
            continue  # transforms/ isn't expected to have subpackages
        module = importlib.import_module(f"{package_name}.{info.name}")
        func = getattr(module, info.name, None)
        if func is not None:
            setattr(package, info.name, func)
