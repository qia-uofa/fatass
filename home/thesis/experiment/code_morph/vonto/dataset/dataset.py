"""Base class and shared infrastructure for every vonto Phase-0 dataset.

Every "Generate" dataset (`SynonymsDataset`, `ListElicitationDataset`,
`TwentyQuestionsDataset` — each its own ``xxx_dataset.py`` in this package)
draws its content from one shared category/keyword universe (`CATEGORY`/
`sample`, `vonto.twenty_questions`) instead of each hardcoding its own fixed
list; the one "Download" dataset (`TriviaQA`) shares a swappable question-
phrasing mechanism (`DIRECT_QUESTION`/`BINARY_JUDGMENT_QUESTION`) instead of
inventing its own prompt wording.

Scope note: ``generate()`` only ever *prepares* seeds — actually asking the
model an `Inquiry` is a later phase's concern
(`vonto.observation_method`/`vonto.ground_truth`, which read and grade a
`Trial`, never a bare `Seed`), and none of these datasets need a loaded LLM to
prepare their seeds *except* `TwentyQuestionsDataset`: its games are fully
played out during ``generate()`` itself, because a game's own turn-by-turn
history is needed to ask its next question at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import twenty_questions as TQ

#: The shared category universe every "Generate" dataset draws from —
#: `twenty_questions.py`'s own 10 WordNet synsets (7 concrete, 3 abstract).
CATEGORY: tuple[str, ...] = TQ.CATEGORIES


def sample(category: str, n: int, seed: int = 0) -> tuple[str, ...]:
    """``n`` unique keywords from ``category``, by natural frequency, no repeats."""
    return TQ.sample_natural_keywords(n=n, seed=seed, category=category)


@dataclass
class Inquiry:
    """One thing to actually ask the model: the text, its sampling temperature,
    and the seed to reproduce it (``None`` for a deterministic, no-sampling ask).

    ``stop_strings`` defaults to ``("\\n\\n",)`` — a blank line is a good
    boundary for a short factual answer (TriviaQA/Synonyms-shaped questions),
    which is what this default was built for. A dataset whose answer is
    naturally long/multi-line (e.g. a 20-item list, one per line) needs to
    override this to ``None`` on its own `Inquiry`, or generation stops at
    the first blank line the model writes — typically the transition *into*
    the actual content, before any of it exists yet.
    """

    question: str
    temperature: float
    generation_seed: int | None
    stop_strings: tuple[str, ...] | None = ("\n\n",)


@dataclass
class Trial:
    """The outcome of actually running one seed's `Inquiry` against a model —
    the missing link between Phase-0 dataset preparation (this package) and
    Phase 1 (`vonto.observation_method`/`vonto.ground_truth`), which read and
    grade a `Trial`, never a bare `Seed`.

    ``value`` (not ``label``) holds a `GroundTruth`'s ``[0, 1]`` score once
    graded — a float throughout, even for an inherently binary ground truth
    (which just settles on ``0.0``/``1.0``), so it's always directly
    comparable to a Likert self-report's own midpoint value.

    ``answer_logprobs`` and ``answer_entropies`` are both filled in during the
    original generation, one entry per answer token, at zero extra model
    cost: ``answer_logprobs[i]`` is ``log P(token_i)`` for the token actually
    sampled at step ``i``; ``answer_entropies[i]`` is the Shannon entropy of
    that step's *full* next-token distribution (every token the model could
    have produced there, not just the one it did) — both read off the same
    per-step logits, just reduced differently. Grading (`ProbabilityGT`,
    `EntropyGT`) never re-runs the model; it only aggregates these.

    **A constraint this ``response`` is not itself checked against**
    (reproduction guidebook §2.6): once ``response`` is stitched into a
    Phase-1 self-report prompt (`vonto.observation_method.LikertOM`), the
    newline right after it (PANL) needs to be its own isolated token for that
    prompt's position semantics to hold — which fails whenever ``response``
    itself ends in punctuation (the trailing character merges into one
    ``".\\n"`` token instead of a clean ``"\\n"``). Generation doesn't filter
    on this (a `Trial` with a punctuation-ending answer is still a perfectly
    valid `Trial` on its own), so any consumer doing position-level analysis
    — as opposed to just reading the aggregate self-report value — must check
    it explicitly, per trial, with
    `vonto.calibration.observation.verify_positions`.
    """

    seed: object
    inquiry: Inquiry
    response: str = ""
    answer_logprobs: list = field(default_factory=list)
    answer_entropies: list = field(default_factory=list)
    observed: object = None
    value: float | None = None


def DIRECT_QUESTION(question: str, answer: str) -> str:
    """Ask the question as-is; ``answer`` is unused (kept for a uniform
    signature with `BINARY_JUDGMENT_QUESTION`)."""
    return question


def BINARY_JUDGMENT_QUESTION(question: str, answer: str) -> str:
    """Ask whether ``answer`` is the right answer to ``question``, yes/no."""
    return f'Is the answer to "{question}" "{answer}"? Answer Yes or No.'


class Dataset:
    """Base for every vonto Phase-0 dataset: a list of ``seeds``, ``generate()``
    to build them, and ``inquiry(seed)`` to turn one into something askable.

    ``shape_tag()`` names a generation by the parameters that actually define
    its size/content (e.g. ``"Synonyms_n50"``) — ``save``/``load_if_cached``
    key their filename on it, so two differently-shaped generations of the
    same dataset never collide or silently overwrite each other.
    """

    #: The dataclass one seed deserializes into — set by each concrete subclass.
    seed_cls: type | None = None

    def __init__(self) -> None:
        self.seeds: list = []

    def generate(self) -> None:
        raise NotImplementedError

    def inquiry(self, seed) -> Inquiry:
        raise NotImplementedError

    def shape_params(self) -> dict[str, object]:
        """The parameters that define this dataset's shape/size — override per
        subclass with whatever actually varies generation to generation."""
        raise NotImplementedError

    def shape_tag(self) -> str:
        name = type(self).__name__.removesuffix("Dataset")
        params = "".join(f"{key}{value}" for key, value in self.shape_params().items())
        return f"{name}_{params}"

    def _seed_from_dict(self, blob: dict) -> object:
        """Reconstruct one seed from its JSON dict — the default just calls
        ``seed_cls(**blob)``; override for a seed with non-JSON-native fields
        (e.g. a tuple field, which round-trips as a list)."""
        return self.seed_cls(**blob)

    def save(self, dir_path: str | Path) -> Path:
        """Write every seed to disk as JSON, named by `shape_tag()`."""
        from dataclasses import asdict

        path = Path(dir_path) / f"{self.shape_tag()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(s) for s in self.seeds], indent=1))
        return path

    def load_if_cached(self, dir_path: str | Path) -> bool:
        """Load already-generated seeds of this exact shape from disk instead of
        calling `generate()` again, if a matching file exists. Returns whether a
        cache hit happened."""
        path = Path(dir_path) / f"{self.shape_tag()}.json"
        if not path.exists():
            return False
        self.seeds = [self._seed_from_dict(blob) for blob in json.loads(path.read_text())]
        return True
