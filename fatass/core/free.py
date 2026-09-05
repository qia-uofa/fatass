import contextvars
import dataclasses
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from .._internal.logs import get_logger
from .._internal.paths import ENV_PATH, HOME_ROOT
from .._internal.prompts import load_system_prompt
from ..errors import FreeCoercionError, FreeError
from ..resolve import dotenv
from ..node.node import Node

_current_node: contextvars.ContextVar[type[Node]] = contextvars.ContextVar(
    "fatass_current_node"
)

_RESULT_SENTINEL = ".fatass-result.json"

DEFAULT_ALLOWED_TOOLS = "Read,Write,Edit,Glob,Grep,Bash,WebSearch,WebFetch"
"""The full tool grant — unchanged default for any caller that doesn't
pass tools= explicitly. A caller whose prompt doesn't need all of these
(e.g. no network access, no shell) should narrow it, least-privilege."""

_PRIMITIVE_TYPES = (str, int, float, bool, list, dict)

DEFAULT_PERMISSION_MODE = "acceptEdits"
"""Safer than "bypassPermissions": file edits (Read/Write/Edit) are
auto-accepted so a headless run doesn't stall waiting for approval, but
Claude Code's own finer-grained safety checks (e.g. on risky Bash
commands) still apply instead of being skipped outright. A caller whose
prompt genuinely needs unattended shell access can still pass
permission_mode="bypassPermissions" explicitly."""

NO_PROMPT_TEXT = "<no instructions given — wait for further input>"
"""What `modify`/`free`'s CLI substitutes for an omitted or empty prompt
argument, since the agent needs some starting message. Meant for a
non-silent (interactive) call, where a human picks up the conversation
right after; a silent call with no real prompt has nothing to wait on."""


_CLAUDE_BIN_KEY = "FATASS_CLAUDE_BIN"


def _claude_binary() -> str:
    """The `claude` executable to invoke: FATASS_CLAUDE_BIN from
    .fatass/.env if set, else just "claude" (resolved from PATH as
    normal). Needed for environments (e.g. this process's own PATH over
    SSH) where the interactive login shell can find `claude` but the
    PATH actually visible here can't."""
    return dotenv.read(ENV_PATH).get(_CLAUDE_BIN_KEY, "claude")


def _log_token_usage(logger, stdout: str) -> None:
    """`-p --output-format json` includes a top-level `usage` object with
    token counts (and a `total_cost_usd`). Best-effort: never fail the
    call over this parse, since the exact JSON shape is Claude Code's, not
    a contract fatass controls."""
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(parsed, dict):
        return
    usage = parsed.get("usage")
    if usage:
        logger.info(
            "free(): tokens=%s total_cost_usd=%s", usage, parsed.get("total_cost_usd")
        )


def _detached_env() -> dict[str, str]:
    """A copy of the current environment with Claude Code's own
    session-identity variables (CLAUDE_CODE_SESSION_ID,
    CLAUDE_CODE_MESSAGING_SOCKET/_TOKEN, CLAUDECODE, CLAUDE_PID, etc.)
    stripped out.

    `_invoke_claude` spawns a brand-new, independent `claude` subprocess —
    but when fatass itself is being run from inside an already-running
    Claude Code session (e.g. a terminal opened in the VS Code extension,
    or this very command being driven by another agent), those vars are
    already present in this process's own environment and would otherwise
    be inherited by the child unchanged. The `claude` CLI uses them to
    detect and attach to its parent's session, so an uncleaned child
    doesn't start fresh on `prompt` at all — it silently joins the parent
    conversation instead, receiving whatever that session sends it next
    instead of the seeded prompt."""
    return {
        key: value
        for key, value in os.environ.items()
        if not (key == "AI_AGENT" or key.startswith("CLAUDE"))
    }


def _run_in_new_window(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    """Run `command` in its own, visible terminal window, blocking until
    that window's process exits — needed so callers (e.g. free() reading
    back .fatass-result.json right after) can keep treating this
    synchronously, same as the headless path.

    Windows: `creationflags=CREATE_NEW_CONSOLE` asks CreateProcess directly
    for a new console, with no `cmd.exe` involved at all. An earlier
    version shelled out via `cmd /c start "<title>" /wait <command>`
    instead, but that runs the *entire* command line — including a
    system prompt loaded from fatass/prompts/*.md, which routinely
    contains both literal `"` characters and `<`/`>` (the docs' own
    <node.path> placeholder syntax) — back through cmd.exe's own line
    parser. cmd.exe has no idea that a backslash-quote pair from
    list2cmdline() means "literal embedded quote, stay in the same
    quoted/unquoted mode" (that convention is the child process's CRT
    argv parser's job, not cmd's) — it just flips quoted-mode on *every*
    bare `"` it scans. With an even handful of embedded quotes, long
    stretches of the prompt end up on the wrong side of that flip, so any
    `<`/`>` sitting in one of those stretches gets read as real
    redirection syntax instead of literal prompt text, corrupting the
    command before `claude` ever sees it — which is exactly why the
    window would come up with no seed message at all. Spawning directly
    means Python's own list2cmdline() (used for a list `args` regardless
    of creationflags) is the only thing that ever tokenizes `command`,
    matching what the child's CRT-style argv parser expects, with no
    second, incompatible reparser in between. subprocess.run() already
    blocks until the child exits, so no `/WAIT`-equivalent is needed
    either — and a friendly window title comes from `claude`'s own
    `--name` flag (see base_command) rather than a `start "title"` hack.

    There is no equally universal mechanism on macOS/Linux (Terminal.app/
    osascript can't block the same way, and Linux has no single standard
    terminal emulator), so elsewhere this just runs `command` inline in
    whatever terminal this process already has — still a live, watchable
    conversation, just not spawned into a separate window."""
    if platform.system() == "Windows":
        return subprocess.run(
            command, cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    return subprocess.run(command, cwd=cwd, env=env)


def _invoke_claude(
    cwd: Path,
    add_dirs: list[Path],
    prompt: str,
    *,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    system_prompt: str | None = None,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
    effort: str | None = None,
) -> subprocess.CompletedProcess:
    """Run the `claude` CLI, scoped to file-editing tools. Shared by
    `free()` (writable = the current transform's owning node),
    `fatass.topology_ops.scaffold` (writable = wherever a node/transform is
    being scaffolded under fatass/topology/ — a different directory than
    any node's `home/` output, so it can't go through free() itself), and
    `fatass.core.adhoc` (writable = wherever `fatass free` was pointed at).

    `silent=False` (the default) opens a real, human-visible conversation —
    the agent's normal interactive session, seeded with `prompt` as the
    first message — and blocks until it's closed, so a human can watch or
    steer it. `silent=True` instead runs headlessly (`-p --output-format
    json`, output captured, no terminal, exits on its own when done) — pass
    it explicitly for unattended runs (e.g. a `populate.sh`-style batch
    script, or any `returns=...` call whose caller needs to keep going
    without a human closing a window first).

    `effort` (`--effort`): one of "low", "medium", "high", "xhigh", "max"
    — omitted entirely when `None`, same as `model`, so an existing call
    keeps using whatever the `claude` CLI is already configured/defaulted
    to."""
    logger = get_logger()
    add_dirs_str = ", ".join(str(path) for path in add_dirs)

    base_command = [
        _claude_binary(),
        "--allowedTools",
        tools,
        "--permission-mode",
        permission_mode,
    ]
    for path in add_dirs:
        base_command += ["--add-dir", str(path)]
    if system_prompt:
        base_command += ["--append-system-prompt", system_prompt]
    if model:
        base_command += ["--model", model]
    if effort:
        base_command += ["--effort", effort]

    if silent:
        command = base_command + ["-p", prompt, "--output-format", "json"]
        logger.info(
            "free(): cwd=%s add_dirs=[%s] silent=True permission_mode=%s model=%s "
            "effort=%s tools=%s prompt=%r",
            cwd,
            add_dirs_str,
            permission_mode,
            model,
            effort,
            tools,
            prompt,
        )
        try:
            result = subprocess.run(
                command, cwd=cwd, capture_output=True, text=True, env=_detached_env()
            )
        except FileNotFoundError as exc:
            raise FreeError("the `claude` CLI was not found on PATH") from exc

        logger.info("free(): exit=%s", result.returncode)
        logger.info("free(): stdout=%r", result.stdout)
        logger.info("free(): stderr=%r", result.stderr)
        _log_token_usage(logger, result.stdout)
        return result

    command = base_command + ["--name", "Claude", prompt]
    logger.info(
        "free(): cwd=%s add_dirs=[%s] silent=False permission_mode=%s model=%s "
        "effort=%s tools=%s prompt=%r (interactive session)",
        cwd,
        add_dirs_str,
        permission_mode,
        model,
        effort,
        tools,
        prompt,
    )
    try:
        result = _run_in_new_window(command, cwd=cwd, env=_detached_env())
    except FileNotFoundError as exc:
        raise FreeError("the `claude` CLI was not found on PATH") from exc

    logger.info("free(): exit=%s (interactive session closed)", result.returncode)
    logger.info("free(): token usage unavailable — interactive sessions aren't captured")
    return result


def _leaf_asset_dirs(node: type[Node]) -> list[Path]:
    """The asset dirs of `node`'s leaf descendants — nodes with no
    sub-nodes of their own under fatass/topology/ — or just `node`'s own
    dir if it has none. Structural (non-leaf) nodes hold no real data by
    convention, only their leaves do, so a dependency on a non-leaf node
    grants read access to exactly its leaves' directories rather than one
    directory covering its whole subtree (which would also cover
    anything, however incidental, sitting directly in an intermediate
    node's own dir).

    Duck-typed like the rest of this module: a `Chain` item (a bare
    `_ChainItem`, or the dynamically-derived per-index subclass
    `_ChainItem.__getattr__` returns — see core/chain.py) has no
    resolvable fatass/topology/ path of its own, since it's already one
    concrete, specific piece of data rather than a browsable subtree — so
    it's always treated as its own single leaf. Note a bare
    `_ChainItem` doesn't just lack `_topology_path()` — its own
    `__getattr__` is a catch-all that turns *any* unrecognized attribute
    probe (including this one) into an attempted schema-child lookup, so
    the failure here isn't always a clean AttributeError; catching
    Exception broadly is deliberate, not laziness."""
    from ..topology_ops.scaffold import _all_node_paths  # local import: avoid a cycle

    try:
        root = node._topology_path()
    except Exception:
        return [node._assets_dir()]

    subtree = [p for p in _all_node_paths() if p == root or p.startswith(root + ".")]
    leaves = [p for p in subtree if not any(q.startswith(p + ".") for q in subtree)]
    return [HOME_ROOT / leaf.replace(".", "/") for leaf in leaves]


def free(
    readable: list[Node],
    prompt: str,
    returns: type | None = None,
    *,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
    effort: str | None = None,
) -> Any:
    """Invoke the Claude CLI agent.

    `writable` is not a parameter: a transform can only ever write into the
    `home/` directory of the node it belongs to, resolved implicitly from
    the transform currently running (see fatass/transform.py).
    """
    try:
        owning_node = _current_node.get()
    except LookupError as exc:
        raise FreeError(
            "free() was called outside of a running transform "
            "(no owning node in context)"
        ) from exc

    writable_dir = owning_node._assets_dir()
    writable_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = prompt
    if returns is str:
        full_prompt += (
            f"\n\nWhen finished, write your final result to a file named "
            f"{_RESULT_SENTINEL} in the current directory, as plain raw text "
            f"— write the text directly, with no surrounding quotes and no "
            f"JSON escaping of any kind."
        )
    elif returns is not None:
        full_prompt += (
            f"\n\nWhen finished, write your final result to a file named "
            f"{_RESULT_SENTINEL} in the current directory, as "
            f"{_shape_hint(returns)}."
        )

    add_dirs = list(dict.fromkeys(d for node in readable for d in _leaf_asset_dirs(node)))
    result = _invoke_claude(
        cwd=writable_dir,
        add_dirs=add_dirs,
        prompt=full_prompt,
        permission_mode=permission_mode,
        silent=silent,
        system_prompt=load_system_prompt("transform"),
        model=model,
        tools=tools,
        effort=effort,
    )

    if result.returncode != 0:
        raise FreeError(
            f"claude CLI exited with {result.returncode}: {result.stderr}"
        )

    if returns is None:
        return None

    sentinel_path = writable_dir / _RESULT_SENTINEL
    if not sentinel_path.exists():
        raise FreeCoercionError(
            f"expected {_RESULT_SENTINEL} in {writable_dir}, agent didn't "
            f"write one"
        )
    if returns is str:
        raw = sentinel_path.read_text(encoding="utf-8")
    else:
        try:
            raw = json.loads(sentinel_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FreeCoercionError(
                f"{_RESULT_SENTINEL} is not valid JSON: {sentinel_path.read_text(encoding='utf-8')!r}"
            ) from exc
    sentinel_path.unlink(missing_ok=True)

    return _coerce(raw, returns)


def free_topology(
    cwd: Path,
    prompt: str,
    *,
    add_dirs: list[Path] = [],
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    silent: bool = False,
    system_prompt: str | None = None,
    model: str | None = None,
    tools: str = DEFAULT_ALLOWED_TOOLS,
) -> subprocess.CompletedProcess:
    """Invoke the Claude CLI to write under fatass/topology/ itself — a
    node's own file, a transform file, or anything else there.

    `free()` can't do this: it always writes into the *currently running
    transform's* owning node's `home/` directory, resolved from context,
    and topology/ isn't that. This has no such restriction — `cwd` says
    directly where to write, callable any time, not only from inside a
    transform.

    No other directory is granted by default (`add_dirs=[]`) — deliberately
    not the whole topology tree: on a topology with several populated
    example pipelines, that meant every single-function edit paid to read
    hundreds of thousands of tokens' worth of unrelated nodes just to
    infer the file conventions by example. Those conventions are static
    and now live in the `create`/`modify` system prompts
    (`fatass/prompts/conventions.md`) instead, so the agent doesn't need
    read access to other nodes to follow them — it just can't see or
    depend on their actual file layout or content anymore, which a
    prompt author should keep in mind when writing --prompt text that
    references "see how X does it". `add_dirs` is the one deliberate,
    narrow exception: `refine_transform` passes a transform's already-
    declared dependency nodes' own topology directories through it, so
    the agent can read those specific nodes (still read-only — `cwd`
    stays the only writable directory) instead of every unrelated node.

    Used by `fatass.topology_ops.scaffold` (behind the `create`/`modify` CLI commands)
    to flesh out or edit a node/transform file with a prompt.
    """
    result = _invoke_claude(
        cwd=cwd,
        add_dirs=add_dirs,
        prompt=prompt,
        permission_mode=permission_mode,
        silent=silent,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
    )
    if result.returncode != 0:
        raise FreeError(f"claude CLI exited with {result.returncode}: {result.stderr}")
    return result


def result_summary(result: subprocess.CompletedProcess) -> str | None:
    """The agent's own final text summary from a `silent=True` call's
    captured `-p --output-format json` stdout (that JSON's top-level
    `"result"` field), or None for an interactive call (nothing is
    captured for those) or if the field isn't present. Best-effort, same
    as `_log_token_usage` — the exact JSON shape is Claude Code's own, not
    a contract fatass controls."""
    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    summary = parsed.get("result")
    return summary if isinstance(summary, str) else None


def _shape_hint(returns: type) -> str:
    if returns is str:
        return 'a bare JSON string, e.g. "your text here" — not an object wrapping it'
    if returns is int or returns is float:
        return "a bare JSON number, not an object wrapping it"
    if returns is bool:
        return "a bare JSON boolean (true/false), not an object wrapping it"
    if returns is list:
        return "a JSON array"
    if returns is dict:
        return "a JSON object"
    if dataclasses.is_dataclass(returns):
        fields = ", ".join(f.name for f in dataclasses.fields(returns))
        return f"a JSON object with exactly these keys: {fields}"
    return f"JSON matching {returns.__name__}"


def _coerce(value: Any, returns: type) -> Any:
    if returns in _PRIMITIVE_TYPES:
        if not isinstance(value, returns):
            raise FreeCoercionError(
                f"expected {returns.__name__}, got {type(value).__name__}"
            )
        return value
    if dataclasses.is_dataclass(returns):
        if not isinstance(value, dict):
            raise FreeCoercionError(
                f"expected an object for {returns.__name__}, got "
                f"{type(value).__name__}"
            )
        try:
            return returns(**value)
        except TypeError as exc:
            raise FreeCoercionError(
                f"couldn't build {returns.__name__} from result: {exc}"
            ) from exc
    raise FreeCoercionError(f"unsupported returns type: {returns!r}")
