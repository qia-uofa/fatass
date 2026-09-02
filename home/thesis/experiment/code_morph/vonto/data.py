"""Real, downloaded datasets — as opposed to `vonto.dataset`'s
procedurally generated seeds."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import config as cfg


@dataclass
class QuestionItem:
    """One question with its accepted answers."""

    qid: str
    question: str
    answers: tuple[str, ...] = ()
    meta: dict = field(default_factory=dict)


def load_triviaqa(path: Path | None = None, limit: int | None = None) -> list[QuestionItem]:
    """Load the TriviaQA ``rc.nocontext`` validation split already saved to disk
    at `config.TRIVIAQA_DISK` (a ``datasets.Dataset.save_to_disk()`` dump) —
    this reads what's already there, it does not download anything itself.
    Deduplicated on normalized question text, since the raw split repeats a
    handful of questions verbatim.
    """
    from datasets import load_from_disk

    path = path or cfg.TRIVIAQA_DISK
    if not path.exists():
        raise FileNotFoundError(
            f"TriviaQA is not at {path} — save the rc.nocontext validation split "
            "there (datasets.Dataset.save_to_disk) before calling this."
        )
    ds = load_from_disk(str(path))
    items: list[QuestionItem] = []
    seen: set[str] = set()
    for row in ds:
        question = row["question"].strip()
        normalized = " ".join(question.lower().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(
            QuestionItem(
                qid=row["question_id"],
                question=question,
                answers=tuple(row["answer"]["aliases"]),
            )
        )
        if limit and len(items) >= limit:
            break
    return items
