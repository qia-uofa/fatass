"""TriviaQA: downloaded-and-loaded, with a swappable question phrasing — see
`TriviaQA`'s docstring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..data import load_triviaqa
from .dataset import DIRECT_QUESTION, Dataset, Inquiry


@dataclass(frozen=True)
class TriviaQASeed:
    trivia_question: str
    answer: str
    #: Every accepted alias for this question, not just ``answer`` (its own
    #: first alias) — the paper's own grader is fed "the gold answer aliases"
    #: (plural, §2.3.1), since TriviaQA questions often have several
    #: acceptable phrasings; `answer` alone stays the single string other
    #: call sites (question phrasing, `ChallengeGT`'s composed evidence) need.
    aliases: tuple[str, ...] = ()


class TriviaQA(Dataset):
    """`generate()` downloads-and-loads: `data.load_triviaqa` already handles
    both (raising if the on-disk copy isn't there)."""

    seed_cls = TriviaQASeed

    def shape_params(self) -> dict[str, object]:
        return {"limit": self.limit}

    def __init__(self, limit: int | None = 100, raw_question: Callable[[str, str], str] = DIRECT_QUESTION) -> None:
        super().__init__()
        self.limit = limit
        self.raw_question = raw_question

    def generate(self) -> None:
        for item in load_triviaqa(limit=self.limit):
            answer = item.answers[0] if item.answers else ""
            self.seeds.append(TriviaQASeed(item.question, answer, tuple(item.answers)))

    def inquiry(self, seed: TriviaQASeed) -> Inquiry:
        # temperature=0 -- greedy, matching the paper's own "greedy decoding,
        # temperature = 0" requirement (reproduction guidebook §2.1, §2.2);
        # this dataset in particular is the paper's own §3 calibration
        # dataset, so this isn't just a stylistic default here.
        # `generate_trial` now actually samples at whatever temperature it's
        # given, so this can no longer be a nonzero placeholder the way it
        # used to be before that was wired up.
        return Inquiry(self.raw_question(seed.trivia_question, seed.answer), 0.0, 0)
