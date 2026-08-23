from pathlib import Path

from ._paths import NODES_ROOT, TOPOLOGY_ROOT
from .errors import FreeError
from .free import _invoke_claude

_ROOTS = {"nodes": NODES_ROOT, "topology": TOPOLOGY_ROOT}


def _resolve(target: str) -> Path:
    if "." not in target:
        raise ValueError(f"expected 'nodes.<path>' or 'topology.<path>', got {target!r}")
    root_name, rel = target.split(".", 1)
    root = _ROOTS.get(root_name)
    if root is None:
        raise ValueError(
            f"expected target to start with 'nodes.' or 'topology.', got {target!r}"
        )
    target_dir = root / rel.replace(".", "/")
    if not target_dir.is_dir():
        raise FreeError(f"no directory at {target_dir}")
    return target_dir


def free_at(target: str, prompt: str) -> None:
    """`fatass free` — invoke the Claude CLI with cwd set directly to a
    nodes/ or topology/ directory, bypassing the transform/dependency
    machinery entirely (no owning node, no readable list, no returns
    coercion — just a one-off agent call scoped to that directory)."""
    target_dir = _resolve(target)
    result = _invoke_claude(cwd=target_dir, add_dirs=[], prompt=prompt)
    if result.returncode != 0:
        raise FreeError(f"claude CLI exited with {result.returncode}: {result.stderr}")
