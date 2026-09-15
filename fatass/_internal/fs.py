import os
import shutil
import stat
from pathlib import Path


def copy_dir_contents(src: Path, dst: Path, *, exclude: set[str] = frozenset()) -> None:
    """Copy every child of `src` (skipping names in `exclude`) into
    `dst`, keeping each child's own basename. `dst` is assumed to already
    exist (created empty by the caller). Shared by `Chain.insert()` and
    `Dictionary.set()` — both seed a freshly-created item/entry as a copy
    of their own dummy head's current content (its `.entry` and/or
    declared schema-child directories), skipping whatever reserved,
    kind-specific bookkeeping name(s) the caller's own dummy head might
    also have alongside that real content (Chain's `.next`/temp dirs,
    Dictionary's `.items`)."""
    if not src.is_dir():
        return
    for child in src.iterdir():
        if child.name in exclude:
            continue
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def force_rmtree(path: Path | str, *, ignore_errors: bool = False) -> None:
    """`shutil.rmtree`, but tolerant of Windows' read-only file attribute —
    set on every file inside a `.git/objects/` directory, for one, so a
    node's `home/` containing a git checkout (e.g. a `Repo`-style node,
    or just a clone someone dropped in) makes plain `shutil.rmtree` raise
    `PermissionError` / `OSError: [WinError 5] Access is denied` without
    ever attempting to clear it — see `Chain.pop()`'s real-world failure
    on exactly this.

    Tries a plain `rmtree` first (the common case, no read-only files);
    on any `OSError`, clears the read-only bit across the whole subtree
    and retries once. `shutil.rmtree` already removes whatever it can
    before hitting a blocked file, so the retry only has the leftovers to
    deal with — safe to call repeatedly. Still raises (unless
    `ignore_errors`) if something *other* than a read-only attribute is
    blocking the delete (e.g. a file genuinely in use)."""
    path = Path(path)
    try:
        shutil.rmtree(path)
        return
    except OSError:
        if not path.exists():
            return

    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                (Path(root) / name).chmod(stat.S_IWRITE)
            except OSError:
                pass
    try:
        path.chmod(stat.S_IWRITE)
    except OSError:
        pass

    try:
        shutil.rmtree(path)
    except OSError:
        if not ignore_errors:
            raise
