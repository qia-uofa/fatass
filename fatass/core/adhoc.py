from ..errors import FreeError
from ..resolve.targets import resolve
from .free import _invoke_claude


def free_at(target: str, prompt: str) -> None:
    """`fatass free` — invoke the Claude CLI with cwd set directly to a
    resolved target directory (see fatass.resolve.targets.resolve), bypassing the
    transform/dependency machinery entirely (no owning node, no readable
    list, no returns coercion — just a one-off agent call scoped to that
    directory)."""
    target_dir = resolve(target)
    result = _invoke_claude(cwd=target_dir, add_dirs=[], prompt=prompt)
    if result.returncode != 0:
        raise FreeError(f"claude CLI exited with {result.returncode}: {result.stderr}")
