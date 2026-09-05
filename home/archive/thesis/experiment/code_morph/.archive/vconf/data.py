"""Dataset loading, deduplication and the disjoint partition (§2.3).

Only the filesystem state left behind by ``scripts/setup/_.sh`` is used: the
TriviaQA ``rc.nocontext`` validation split saved at
``$PROJECT_ROOT/data/raw/triviaqa/rc_nocontext_validation``, and the (empty
until provisioned) ``bigmath`` / ``mmlu`` directories.  The manual names no
Hugging Face repo id or configuration for Big-Math and MMLU, so those loaders
read whatever has been saved into their directories and fail loudly otherwise
rather than guessing a source.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config as cfg


class DatasetNotProvisioned(FileNotFoundError):
    """Raised when a dataset directory the setup script created is still empty."""


@dataclass
class QuestionItem:
    """One question with its accepted answers (TriviaQA gold aliases, §2.3.1)."""

    qid: str
    question: str
    answers: tuple[str, ...] = ()
    meta: dict = field(default_factory=dict)


def normalize_question(text: str) -> str:
    """Normalised question text used for deduplication (§2.3.1)."""
    return re.sub(r"\s+", " ", text.strip().lower())


def deduplicate(items: list[QuestionItem]) -> list[QuestionItem]:
    """Remove duplicate questions on normalised question text (§2.3.1)."""
    seen: set[str] = set()
    out: list[QuestionItem] = []
    for item in items:
        key = normalize_question(item.question)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def load_triviaqa(path: Path | None = None, limit: int | None = None) -> list[QuestionItem]:
    """Load the deduplicated TriviaQA ``rc.nocontext`` validation split (§2.3.1, §13 #1)."""
    from datasets import load_from_disk

    path = path or cfg.TRIVIAQA_DISK
    if not Path(path).exists():
        raise DatasetNotProvisioned(
            f"TriviaQA is not at {path}; run scripts/setup/_.sh first (§2.3.1)."
        )
    ds = load_from_disk(str(path))
    items: list[QuestionItem] = []
    for row in ds:
        answer = row.get("answer") or {}
        aliases = tuple(answer.get("normalized_aliases") or answer.get("aliases") or ())
        value = answer.get("value")
        if value and value not in aliases:
            aliases = (value,) + aliases
        items.append(
            QuestionItem(qid=str(row.get("question_id")), question=row["question"], answers=aliases)
        )
        if limit is not None and len(items) >= limit:
            break
    return deduplicate(items)


def load_bigmath(path: Path | None = None) -> list[QuestionItem]:
    """Load Big-Math from ``$PROJECT_ROOT/data/raw/bigmath`` (§2.3.2, §12.3).

    The manual states only that Big-Math is "available on the Hugging Face hub";
    no repo id or configuration is given, and the setup script deliberately left
    the download unspecified.  Save a ``datasets`` directory there (columns
    ``problem``/``answer``) to enable Axis 3.
    """
    return _load_local_dataset(
        path or cfg.BIGMATH_DIR,
        name="Big-Math",
        question_keys=("problem", "question"),
        answer_keys=("answer", "final_answer", "solution"),
    )


def load_mmlu(path: Path | None = None) -> list[QuestionItem]:
    """Load MMLU (``test`` split, all subjects) from ``$PROJECT_ROOT/data/raw/mmlu`` (§13 #14).

    Multiple choice: the question is rendered as the stem plus its lettered
    options and correctness is exact match on the chosen option letter (§2.3.3).
    """
    items = _load_local_dataset(
        path or cfg.MMLU_DIR,
        name="MMLU",
        question_keys=("question",),
        answer_keys=("answer",),
        keep_row=True,
    )
    letters = "ABCD"
    out: list[QuestionItem] = []
    for item in items:
        row = item.meta.get("row", {})
        choices = row.get("choices") or row.get("options") or []
        options = "\n".join(f"{letters[i]}. {choice}" for i, choice in enumerate(choices))
        answer = row.get("answer")
        letter = letters[answer] if isinstance(answer, int) and answer < len(letters) else str(answer)
        out.append(
            QuestionItem(
                qid=item.qid,
                question=f"{item.question}\n{options}" if options else item.question,
                answers=(letter,),
                meta={"subject": row.get("subject"), "choices": list(choices)},
            )
        )
    return out


def _load_local_dataset(
    path: Path,
    name: str,
    question_keys: tuple[str, ...],
    answer_keys: tuple[str, ...],
    keep_row: bool = False,
) -> list[QuestionItem]:
    from datasets import load_from_disk

    path = Path(path)
    candidates = [path] if (path / "state.json").exists() or (path / "dataset_info.json").exists() else sorted(
        p for p in path.glob("*") if p.is_dir()
    )
    if not candidates:
        raise DatasetNotProvisioned(
            f"{name} is not provisioned at {path}. The manual names no Hugging Face "
            f"repo id for {name} (§2.3.2/§2.3.3), so nothing is downloaded "
            "automatically; save a `datasets` directory there to enable this axis."
        )
    ds = load_from_disk(str(candidates[0]))
    items: list[QuestionItem] = []
    for i, row in enumerate(ds):
        question = next((row[k] for k in question_keys if k in row), None)
        answer = next((row[k] for k in answer_keys if k in row), None)
        if question is None:
            raise KeyError(f"{name} rows have none of {question_keys}; found {list(row)}")
        items.append(
            QuestionItem(
                qid=str(row.get("id", i)),
                question=str(question),
                answers=(str(answer),) if answer is not None else (),
                meta={"row": dict(row)} if keep_row else {},
            )
        )
    return deduplicate(items)


def load_dataset_items(dataset: str, limit: int | None = None) -> list[QuestionItem]:
    """Dispatch on the dataset name used in :class:`~vconf.config.RunConfig`."""
    if dataset == "triviaqa":
        return load_triviaqa(limit=limit)
    if dataset == "bigmath":
        items = load_bigmath()
    elif dataset == "mmlu":
        items = load_mmlu()
    elif dataset.startswith("benzon:"):
        items = _load_benzon_dataset(dataset[len("benzon:"):])
    else:
        raise KeyError(f"unknown dataset: {dataset!r}")
    return items[:limit] if limit else items


def _load_benzon_dataset(name: str) -> list[QuestionItem]:
    """Dispatch for ``benzon:<name>`` datasets (plan_benzon.md).

    Deferred import: :mod:`vconf.benzon_data` is only needed for this one
    dataset family, so every other ``load_dataset_items`` call stays free of
    importing it.
    """
    from . import benzon_data

    if name == "ontology_trivials":
        return benzon_data.load_ontology_trivials()
    if name == "synonyms":
        return benzon_data.load_synonym_pairs()
    if name == "list_elicitation":
        return benzon_data.load_list_elicitation_items()
    if name == "philpapers":
        return benzon_data.load_philpapers()
    if name == "ethics_commonsense":
        return benzon_data.load_ethics_commonsense()
    if name == "ethics_deontology":
        return benzon_data.load_ethics_deontology()
    if name == "ethics_justice":
        return benzon_data.load_ethics_justice()
    if name == "ethics_virtue":
        return benzon_data.load_ethics_virtue()
    if name == "ethics_utilitarianism":
        return benzon_data.load_ethics_utilitarianism()
    raise KeyError(f"unknown benzon dataset: {name!r}")


# --------------------------------------------------------------------------- #
# Disjoint partition (§2.3.4)
# --------------------------------------------------------------------------- #


@dataclass
class Partition:
    """The mutually disjoint subsets required by §2.3.4, built once and recorded."""

    activation: list[QuestionItem]
    calibration: list[QuestionItem]
    test: list[QuestionItem]

    def sizes(self) -> dict[str, int]:
        return {
            "activation": len(self.activation),
            "calibration": len(self.calibration),
            "test": len(self.test),
        }

    def to_json(self) -> dict:
        return {
            name: [item.qid for item in getattr(self, name)]
            for name in ("activation", "calibration", "test")
        }


def partition_pool(
    items: list[QuestionItem],
    activation_n: int = cfg.ACTIVATION_SET_N,
    calibration_n: int = cfg.CALIBRATION_N,
    test_n: int | None = None,
    seed: int = cfg.SEED,
) -> Partition:
    """Split the deduplicated pool *once*, up front, into disjoint subsets (§2.3.4)."""
    if activation_n + calibration_n > len(items):
        raise ValueError(
            f"pool of {len(items)} questions is too small for "
            f"{activation_n} activation + {calibration_n} calibration trials"
        )
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    activation = shuffled[:activation_n]
    calibration = shuffled[activation_n: activation_n + calibration_n]
    test = shuffled[activation_n + calibration_n:]
    if test_n is not None:
        test = test[:test_n]
    return Partition(activation=activation, calibration=calibration, test=test)


def save_partition(partition: Partition, name: str, directory: Path | None = None) -> Path:
    """Record the partition so every experiment reads the same subsets (§2.3.4)."""
    directory = Path(directory or cfg.PARTITIONS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(json.dumps(partition.to_json(), indent=2))
    return path


def load_partition_ids(name: str, directory: Path | None = None) -> dict[str, list[str]]:
    directory = Path(directory or cfg.PARTITIONS_DIR)
    return json.loads((directory / f"{name}.json").read_text())
