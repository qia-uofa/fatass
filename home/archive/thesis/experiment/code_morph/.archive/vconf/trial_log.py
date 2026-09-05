"""Shared trial.json log for the Phase 0 calibration notebooks
(`notebooks_benzon/phase_0_calibration/`).

Every calibration notebook (1_commitment, 2_nuance, 3_synonyms,
4_list_elicitation, 5_twenty_questions) computes some number of
(dataset, OM, GT) -> rho cells and used to just print them — this module
gives them one shared, on-disk record of those cells instead, so a later
notebook (`conclusion.ipynb`) can read back everything already computed,
work out what's still missing, and only compute the gap rather than
re-deriving numbers that already exist. Each notebook calls `upsert` once,
near the end, with whatever cells it just computed; notebooks run
independently (no shared kernel), so `upsert` always reads the current file,
merges in the new records by key, and writes the whole thing back — never
blind-appends, which would duplicate a cell recomputed on a later run.

One record is one matrix cell: ``{"dataset", "om", "gt", "rho", "n"}``. The
key ``(dataset, om, gt)`` is unique — a later `upsert` for the same key
overwrites the earlier value (e.g. a rerun with more trials). ``rho`` is
``None`` (serialized ``null``) for a *deliberately* NaN cell (the self-report
collapsed to one class — a real, reportable result, not a missing one); a
cell that was never attempted at all simply has no record.

``load``/``upsert`` default to the caller's current working directory
(``_default_path``), but every notebook in `phase_0_calibration/` passes an
explicit ``path=`` instead, pointing at ``cache/<model>/trial.json`` — the
notebooks all share one directory now (picking a model via that directory's
own `config.json`, not via which directory they live in), so a bare
cwd-relative default would silently merge two different models' self-report
results under the same (dataset, om, gt) keys. The default stays available
for ad-hoc/REPL use outside the notebooks.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


def _default_path() -> Path:
    return Path.cwd() / "trial.json"


def __getattr__(name: str):
    # PEP 562: makes `trial_log.DEFAULT_PATH` (e.g. in a notebook's own
    # `print(f"...{TL.DEFAULT_PATH}")`) resolve against *that caller's* cwd
    # at access time, not a value frozen at this module's import time.
    if name == "DEFAULT_PATH":
        return _default_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

#: Canonical ``gt`` key for each ground truth's display name as it appears in
#: a notebook's own `rho_matrix`/`full_matrix` DataFrame columns — a stable,
#: snake_case join key so "answer logit" (1_commitment/3_synonyms) and
#: "TriviaQA x binary entropy" (2_nuance, dataset baked into the column name)
#: both resolve to the one record `conclusion.ipynb` looks up. The canonical
#: (right-hand) keys, and the on-disk `trial.json` records themselves, still
#: use the original short names (`gegt`/`hegt`/...) — only the *display*
#: names (left-hand) were renamed, so no already-logged record needed
#: rewriting.
GT_KEY: dict[str, str] = {
    "labeled correctness": "correctness",
    "answer logit": "logit_gt",
    "self challenge resistance": "gegt",
    "labeled challenge resistance": "hegt",
    "binary entropy": "entropy_gt",
    "nonbinary logit": "nbgt",
}
#: Renamed from the original OM names (`committed`/`committed_defined`/
#: `multiverse`/`evidence_drop`) — unlike `GT_KEY` above, OMs have no
#: separate display/storage-key indirection, so this rename *is* the
#: canonical key, matching `trial.json`'s own ``"om"`` field values.
GENERAL_OMS: tuple[str, ...] = (
    "confidence",
    "commitment", "commitment_defined", "commitment_parallel", "commitment_challenge",
    "nuance", "nuance_ambiguity", "nuance_certainty", "nuance_defined",
)
GENERAL_GTS: tuple[str, ...] = ("correctness", "logit_gt", "gegt", "hegt", "entropy_gt", "nbgt")
GENERAL_DATASETS: tuple[str, ...] = ("triviaqa", "ontology_trivials", "synonyms")


def load(path: Path | str | None = None) -> list[dict]:
    """All records currently on disk, or ``[]`` if the file doesn't exist yet."""
    path = Path(path) if path is not None else _default_path()
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _key(record: dict) -> tuple[str, str, str]:
    return (record["dataset"], record["om"], record["gt"])


def upsert(records: list[dict], path: Path | str | None = None) -> list[dict]:
    """Merge ``records`` into the on-disk log by ``(dataset, om, gt)`` and
    write the result back, sorted for a stable diff. A ``rho`` of ``float('nan')``
    is written as ``null`` (JSON has no NaN); read back as ``float('nan')``.
    Returns the full merged record list.
    """
    path = Path(path) if path is not None else _default_path()
    existing = {_key(r): r for r in load(path)}
    for r in records:
        rho = r.get("rho")
        r = {**r, "rho": None if (rho is None or (isinstance(rho, float) and math.isnan(rho))) else rho}
        existing[_key(r)] = r
    merged = sorted(existing.values(), key=_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    return merged


def as_lookup(records: list[dict]) -> dict[tuple[str, str, str], float]:
    """``(dataset, om, gt) -> rho`` (``NaN`` for a stored ``null``), for quick
    "is this cell already computed" checks."""
    return {_key(r): (float("nan") if r["rho"] is None else r["rho"]) for r in records}
