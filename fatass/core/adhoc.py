from .._internal.prompts import load_system_prompt
from ..errors import FreeError
from ..resolve.targets import resolve
from .free import DEFAULT_ALLOWED_TOOLS, DEFAULT_PERMISSION_MODE, _invoke_claude


def free_at(
    target: str,
    prompt: str,
    *,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> None:
    """`fatass free` — invoke the Claude CLI with cwd set directly to a
    resolved target directory (see fatass.resolve.targets.resolve), bypassing the
    transform/dependency machinery entirely (no owning node, no readable
    list, no returns coercion — just a one-off agent call scoped to that
    directory)."""
    target_dir = resolve(target)
    result = _invoke_claude(
        cwd=target_dir,
        add_dirs=[],
        prompt=prompt,
        permission_mode=permission_mode,
        silent=silent,
        system_prompt=load_system_prompt("free"),
        model=model,
        tools=tools,
    )
    if result.returncode != 0:
        raise FreeError(f"claude CLI exited with {result.returncode}: {result.stderr}")
