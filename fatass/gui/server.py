"""FastAPI server backing `fatass gui` — a thin HTTP wrapper around the
same command dispatch the `shell` REPL uses (`fatass.cli.main`), plus a
read-only endpoint that renders the whole topology as a nested JSON tree
(node class/"badge", subnodes, transforms) for the graph view."""

import contextlib
import io
import shlex
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .._internal.import_tree import reload_all
from ..ls import DependencySummary, TransformInfo, list_node, list_root
from ..resolve.cwd import (
    PAREN_ROOT,
    ROOT,
    display_current_node,
    enter_session,
    exit_session,
    read_current_node,
)
from ..signature import SIMPLE_TYPED, build_sig_data, pathed_signature, render_signature

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="fatass gui")


@app.on_event("startup")
def _start_session() -> None:
    # Session-scoped cwd (like `shell`'s REPL) — a `cd` typed into the GUI
    # only affects this server process, never the shared .fatass/.env
    # file other `fatass` invocations (or another `fatass gui`) read.
    enter_session(read_current_node())


@app.on_event("shutdown")
def _end_session() -> None:
    exit_session()


def _dep_json(dep: DependencySummary) -> dict:
    # Pathed — a dependency can live anywhere in the topology, not just
    # locally nested under the node whose transform declares it, so only
    # a path (not a bare class name) says which node is actually meant.
    return {
        "path": dep.path,
        "class_name": dep.class_name,
        "children": dep.children,
        "pathed_signature": pathed_signature(dep.path, SIMPLE_TYPED, max_depth=0),
    }


def _transform_json(spec: TransformInfo) -> dict:
    return {"name": spec.name, "dependencies": [_dep_json(d) for d in spec.dependencies]}


def _node_json(node_path: str) -> dict:
    """One node's own signature/transforms plus its full subtree,
    recursively — same shape at every depth so the frontend can render
    it with one recursive component. A node that fails to import (a
    mid-edit file, say) still gets a place in the tree instead of taking
    the whole response down with it."""
    try:
        summary = list_node(node_path)
        node_signature = render_signature(build_sig_data(node_path, max_depth=0), SIMPLE_TYPED)
    except Exception as exc:  # noqa: BLE001 - one broken node shouldn't 500 the whole tree
        return {
            "path": node_path,
            "name": node_path.rsplit(".", 1)[-1],
            "class_name": "?",
            "signature": node_path.rsplit(".", 1)[-1],
            "error": str(exc),
            "children": [],
            "transforms": [],
        }

    return {
        "path": node_path,
        "name": node_path.rsplit(".", 1)[-1],
        "class_name": summary.class_name,
        "signature": node_signature,
        "children": [_node_json(f"{node_path}.{name}") for name in summary.children],
        "transforms": [_transform_json(t) for t in summary.transforms],
    }


@app.get("/api/tree")
def get_tree() -> JSONResponse:
    # Only the current node (pwd) and everything under it — never the
    # whole topology at once. At the true root, that "current node" is
    # every top-level node, so the response is still the synthetic
    # "topology" wrapper in that one case; anywhere else it's exactly one
    # real node (the pwd itself, with its own badge/transforms), matching
    # what `fatass ls` would show for a single node rather than `ls (@)`'s
    # flat top-level listing.
    cwd = read_current_node()
    if cwd == ROOT:
        return JSONResponse(
            {
                "path": "",
                "name": ROOT,
                "class_name": "topology",
                "children": [_node_json(name) for name in list_root()],
                "transforms": [],
            }
        )
    return JSONResponse(_node_json(cwd))


@app.get("/api/pwd")
def get_pwd() -> dict:
    return {"cwd": display_current_node()}


@app.get("/api/root")
def get_root() -> dict:
    # The frontend builds absolute-path command lines (menu items, the
    # selection label) itself, so it needs these two sentinel spellings
    # too -- fetched once from here rather than hardcoded as JS literals,
    # so `fatass.resolve.cwd.ROOT`/`PAREN_ROOT` stay the single place
    # that actually defines them.
    return {"root": ROOT, "paren_root": PAREN_ROOT}


class CommandRequest(BaseModel):
    line: str


@app.post("/api/command")
def run_command(req: CommandRequest) -> dict:
    # Deferred import: cli.py imports commands/ (and this module isn't
    # imported by commands/), so this is safe at call time even if a
    # future refactor makes it not safe at module-load time.
    from ..cli import main

    line = req.line.strip()
    if not line:
        return {"ok": True, "output": "", "cwd": display_current_node()}

    buffer = io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = main(shlex.split(line))
        ok = exit_code == 0
    except SystemExit as exc:
        ok = exc.code in (None, 0)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the GUI, don't 500
        ok = False
        buffer.write(f"error: {exc}\n")

    try:
        reload_all("fatass.topology")
    except Exception as exc:  # noqa: BLE001 - same as shell.py's REPL loop
        buffer.write(f"error: {exc}\n")

    return {"ok": ok, "output": buffer.getvalue(), "cwd": display_current_node()}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
