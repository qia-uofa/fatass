"""Phase-0 dataset preparation (`notebooks_benzon/plan.md`'s design guide).

That file's pseudocode is a *feature* description, not code to transcribe — this
module implements what it describes as real, idiomatic Python. Every "Generate"
dataset (`SynonymsDataset`, `ListElicitationDataset`, `TwentyQuestionsDataset`) draws
its content from one shared category/keyword universe (`CATEGORY`/`sample`) instead of
each hardcoding its own fixed list; every "Download" dataset (`TriviaQA`, ...) shares
one raw-question-phrasing mechanism (`DIRECT_QUESTION`/`BINARY_JUDGMENT_QUESTION`)
instead of each inventing its own prompt wording.

Scope note: for `SynonymsDataset`/`ListElicitationDataset`/`TriviaQA`, ``generate()``
only ever *prepares* seeds — actually asking the model an ``Inquiry`` is a later,
Phase-1 concern (and neither needs a loaded LLM: `SynonymsDataset` needs word2vec
vectors, not the model). `TwentyQuestionsDataset` is the one exception: its games are
fully played out during ``generate()`` itself (real model calls, two generations per
turn) rather than deferred, since a game's own history is needed to ask its next
question at all — `inquiry()` still exists on it for building a next-question prompt
from a partial history, but every game `generate()` produces is already complete.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from . import twenty_questions as TQ
from .data import load_triviaqa

#: The shared category universe every "Generate" dataset draws from (plan.md) —
#: `twenty_questions.py`'s own 10 WordNet synsets (7 concrete, 3 abstract) already
#: have exactly this shape, so it's reused rather than redefined.
CATEGORY: tuple[str, ...] = TQ.CATEGORIES


def sample(category: str, n: int, seed: int = 0) -> tuple[str, ...]:
    """``n`` unique keywords from ``category``, by natural frequency, no repeats
    (plan.md) — `twenty_questions.py`'s own Brown-corpus sampler."""
    return TQ.sample_natural_keywords(n=n, seed=seed, category=category)


@dataclass
class Inquiry:
    """One thing to actually ask the model: the text, its sampling temperature, and
    the seed to reproduce it (``None`` for a deterministic, no-sampling ask)."""

    question: str
    temperature: float
    generation_seed: int | None


def DIRECT_QUESTION(question: str, answer: str) -> str:
    """Ask the question as-is; ``answer`` is unused (kept for a uniform signature
    with `BINARY_JUDGMENT_QUESTION`)."""
    return question


def BINARY_JUDGMENT_QUESTION(question: str, answer: str) -> str:
    """Ask whether ``answer`` is the right answer to ``question``, yes/no."""
    return f'Is the answer to "{question}" "{answer}"? Answer Yes or No.'


class Dataset:
    """Base for every Benzon Phase-0 dataset: a list of ``seeds``, ``generate()`` to
    build them, and ``inquiry(seed)`` to turn one into something askable.

    ``shape_tag()`` names a generation by the parameters that actually define its
    size/content (e.g. ``"Synonyms_n5"``) — ``save``/``load_if_cached`` key their
    filename on it, so two differently-shaped generations of the same dataset never
    collide or silently overwrite each other (an all-too-easy mistake with one fixed
    filename per dataset, as `TwentyQuestionsDataset`'s own checkpoint found out the
    hard way — a stale checkpoint written under different ``(k, T)`` settings was
    silently reused, until it added its own shape check).
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
        (e.g. `Game`'s tuple fields, which round-trip as lists)."""
        return self.seed_cls(**blob)

    def save(self, dir_path: str | Path) -> Path:
        """Write every seed to disk as JSON, named by `shape_tag()` (e.g.
        ``Synonyms_n5.json``) — same convention as `pipeline.save_trials`, plus the
        shape-keyed filename."""
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


# --------------------------------------------------------------------------- #
# Generate: Synonyms
# --------------------------------------------------------------------------- #


def download_word2vec_vectors() -> Path:
    """Fetch the raw (non-gensim) GoogleNews word2vec binary via `huggingface_hub` —
    the same download mechanism already used for every model checkpoint in this
    project, just pointed at a mirror of the original file instead of an LLM."""
    from huggingface_hub import hf_hub_download

    return Path(
        hf_hub_download(
            repo_id="NathaNn1111/word2vec-google-news-negative-300-bin",
            filename="GoogleNews-vectors-negative300.bin",
        )
    )


def load_word2vec_vectors(path: str | Path, wanted: set[str]) -> dict[str, np.ndarray]:
    """Read only ``wanted`` words' vectors out of a raw word2vec ``.bin`` file in one
    streaming pass (case-insensitive) — the classic binary format: an ASCII header
    line ``"vocab_size dim"``, then per word, a space-terminated ASCII token
    followed by ``dim`` raw float32 bytes.

    Not gensim: gensim's compiled extensions don't build against this environment's
    Python version (3.14 — its Cython code uses now-removed CPython internals), and
    the only binary wheel pip resolves without compiling is a decade-old release
    incompatible with the scipy already installed. This reimplements just the read
    path actually needed here, in plain numpy, against the *original* file format
    (this dataset never depends on gensim being installed at all).
    """
    path = Path(path)
    wanted_lower = {w.lower() for w in wanted}
    out: dict[str, np.ndarray] = {}
    with open(path, "rb") as f:
        vocab_size, dim = (int(x) for x in f.readline().split())
        vector_bytes = 4 * dim
        remaining = set(wanted_lower)
        for _ in range(vocab_size):
            if not remaining:
                break
            word = bytearray()
            while True:
                ch = f.read(1)
                if ch in (b" ", b""):
                    break
                if ch != b"\n":
                    word.extend(ch)
            raw = f.read(vector_bytes)
            token = word.decode("utf-8", errors="ignore").lower()
            if token in remaining:
                out[token] = np.frombuffer(raw, dtype=np.float32).copy()
                remaining.discard(token)
    return out


def _lexical_relation_pairs(dataset: str, split: str) -> list[tuple[str, str, str]]:
    """``(head, tail, relation)`` triples from one split of
    `relbert/lexical_relation_classification` — five human-annotated lexical-relation
    benchmarks (EVALution, CogALexV, K&H+N, BLESS, ROOT09) bundled by relbert into one
    HF dataset repo, each a small JSONL file (KBs–few MB), not the 2.25GB PPDB dump
    also considered for this."""
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        repo_id="relbert/lexical_relation_classification",
        filename=f"dataset/{dataset}/{split}.jsonl",
        repo_type="dataset",
    )
    out = []
    with open(path) as f:
        for line in f:
            blob = json.loads(line)
            out.append((blob["head"], blob["tail"], blob["relation"]))
    return out


@dataclass(frozen=True)
class SynonymSeed:
    wordpair: tuple[str, str]
    relation: str  # "twin" | "sibling" | "relative"


class SynonymsDataset(Dataset):
    """``n`` word pairs per relation tier, drawn directly from human-annotated
    lexical-relation benchmarks instead of sampling a keyword and generating a
    related word for it (plan.md's original design, and two revisions after it —
    see git history): procedurally *generating* a synonym via word2vec/WordNet kept
    producing edge-case failures (wrong senses, degenerate fallbacks); real labeled
    pairs from academic benchmarks sidestep that. Pairs need not share any word
    across tiers — "equal pairs", not "one keyword's three relations".

    - **twin** (interchangeable) — EVALution's ``"Synonym"`` + CogALexV's ``"SYN"``
      pairs, human-annotated. Filtered further to require word2vec cosine
      similarity >= ``min_twin_similarity``: a labeled "Synonym" pair isn't
      automatically *interchangeable* (EVALution itself has ``("write", "mark")``,
      which share a sense but don't drop into each other's place in most
      sentences) — this rejects the loosest of the labeled pairs, on the
      assumption that a genuinely interchangeable pair should also look close
      distributionally.
    - **sibling** (same meaning, not interchangeable) — K&H+N's ``"sibl"`` pairs: an
      established co-hyponym relation in the lexical-relations literature (two
      words sharing an immediate parent category, e.g. "cat"/"dog" under
      "mammal") that already carries the exact name "sibling" there.
    - **relative** (similar meaning) — BLESS's ``hyper``/``mero``/``attri``/``event``
      pairs (explicitly excluding BLESS's own ``coord``, which is the same
      co-hyponym relation as "sibling", and ``random``, which isn't related at
      all): genuinely related, but neither synonymous nor co-hyponyms.
    """

    seed_cls = SynonymSeed

    def shape_params(self) -> dict[str, object]:
        return {"n": self.n}

    def _seed_from_dict(self, blob: dict) -> SynonymSeed:
        return SynonymSeed(wordpair=tuple(blob["wordpair"]), relation=blob["relation"])

    def __init__(
        self, word2vec_path: str | Path, n: int, min_twin_similarity: float = 0.25, rng_seed: int = 0,
    ) -> None:
        super().__init__()
        self.word2vec_path = word2vec_path
        self.n = n
        self.min_twin_similarity = min_twin_similarity
        self.rng_seed = rng_seed

    def _similarity(self, vectors: dict[str, np.ndarray], a: str, b: str) -> float:
        if a.lower() not in vectors or b.lower() not in vectors:
            return -1.0
        va, vb = vectors[a.lower()], vectors[b.lower()]
        return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))

    def generate(self) -> None:
        twin_pool = list(
            {
                (h, t)
                for h, t, r in _lexical_relation_pairs("EVALution", "train")
                if r == "Synonym"
            }
            | {(h, t) for h, t, r in _lexical_relation_pairs("CogALexV", "train") if r == "SYN"}
            | {(h, t) for h, t, r in _lexical_relation_pairs("CogALexV", "test") if r == "SYN"}
        )
        sibling_pool = list(
            {
                (h, t)
                for split in ("train", "val", "test")
                for h, t, r in _lexical_relation_pairs("K&H+N", split)
                if r == "sibl"
            }
        )
        relative_pool = list(
            {
                (h, t)
                for h, t, r in _lexical_relation_pairs("BLESS", "train")
                if r in ("hyper", "mero", "attri", "event")
            }
        )

        vectors = load_word2vec_vectors(self.word2vec_path, {w for pair in twin_pool for w in pair})
        filtered_twin = [p for p in twin_pool if self._similarity(vectors, *p) >= self.min_twin_similarity]
        dropped = len(twin_pool) - len(filtered_twin)
        if dropped:
            print(
                f"[SynonymsDataset] dropped {dropped}/{len(twin_pool)} 'Synonym'-labeled pairs below "
                f"word2vec similarity {self.min_twin_similarity} (not genuinely interchangeable)"
            )

        rng = np.random.default_rng(self.rng_seed)
        for pool, relation in [(filtered_twin, "twin"), (sibling_pool, "sibling"), (relative_pool, "relative")]:
            if len(pool) < self.n:
                print(f"[SynonymsDataset] only {len(pool)}/{self.n} '{relation}' pairs available")
            for i in rng.choice(len(pool), size=min(self.n, len(pool)), replace=False):
                self.seeds.append(SynonymSeed(tuple(pool[i]), relation))

    def inquiry(self, seed: SynonymSeed) -> Inquiry:
        a, b = seed.wordpair
        return Inquiry(f'Do "{a}" and "{b}" mean the same thing?', 0.7, None)


# --------------------------------------------------------------------------- #
# Generate: List elicitation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ListElicitationSeed:
    keyword: str
    temperature: float
    generation_seed: int


class ListElicitationDataset(Dataset):
    """One seed per sampled keyword: a random sampling temperature and generation
    seed, not a chosen list of items — the actual list only comes into existence
    later, when `inquiry(seed)`'s prompt is actually sent to the model.
    """

    seed_cls = ListElicitationSeed

    def shape_params(self) -> dict[str, object]:
        return {"n": self.n, "k": self.k}

    def __init__(self, n: int, k: int, rng_seed: int = 0) -> None:
        super().__init__()
        self.n, self.k = n, k
        self._rng = np.random.default_rng(rng_seed)

    def generate(self) -> None:
        for category in CATEGORY:
            keywords = sample(category, self.n)
            for keyword in keywords:
                temperature = float(self._rng.uniform(0.0, 1.0))
                generation_seed = int(self._rng.integers(0, 2**31))
                self.seeds.append(ListElicitationSeed(keyword, temperature, generation_seed))

    def inquiry(self, seed: ListElicitationSeed) -> Inquiry:
        return Inquiry(
            f"Give me a list of {self.k} things, starting with {seed.keyword}.",
            seed.temperature,
            seed.generation_seed,
        )


# --------------------------------------------------------------------------- #
# Generate: Twenty questions
# --------------------------------------------------------------------------- #


@dataclass
class Game:
    """One played-out 20-Questions game. ``history`` is the full turn-by-turn
    transcript, played during `TwentyQuestionsDataset.generate()` itself (dataset
    preparation), not deferred to a later phase."""

    keywords: tuple[str, ...]
    secret: str
    T: int
    history: list = field(default_factory=list)  # [(question, answer), ...]

    def history_str(self) -> str:
        return "\n".join(f"Q: {q}\nA: {a}" for q, a in self.history) or "(no questions yet)"


def _generate_text(loaded, prompt: str | list[dict[str, str]], max_new_tokens: int) -> str:
    """One greedy generation — chat-templated if ``prompt`` is a message list
    (`twenty_questions.build_conversation_for_next_question`'s output), raw text
    otherwise (`build_partition_prompt`'s)."""
    import torch

    messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
    text = loaded.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    with torch.no_grad():
        out = loaded.model.generate(
            **enc, max_new_tokens=max_new_tokens, do_sample=False, temperature=None, top_p=None,
            top_k=None, repetition_penalty=1.0, pad_token_id=loaded.tokenizer.pad_token_id,
        )
    new_tokens = out[:, enc["input_ids"].shape[1]:]
    return loaded.tokenizer.decode(new_tokens[0], skip_special_tokens=True).strip()


class TwentyQuestionsDataset(Dataset):
    """Plays ``len(CATEGORY) * n_games`` full 20-Questions games at generation time
    (real model calls: two generations per turn, ``T`` turns per game) — expensive
    enough that progress checkpoints to ``checkpoint_path`` after every game, so an
    interrupted run resumes instead of replaying already-played games.
    """

    seed_cls = Game

    def shape_params(self) -> dict[str, object]:
        return {"n_games": self.n_games, "k": self.k, "T": self.T}

    def _seed_from_dict(self, blob: dict) -> Game:
        return Game(keywords=tuple(blob["keywords"]), secret=blob["secret"], T=blob["T"],
                    history=[tuple(turn) for turn in blob["history"]])

    def __init__(
        self, loaded, n_games: int, k: int, T: int, rng_seed: int = 0,
        checkpoint_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.loaded = loaded
        self.n_games, self.k, self.T = n_games, k, T
        self.rng_seed = rng_seed
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

    def _play_one_game(self, keywords: tuple[str, ...], secret: str) -> Game:
        history: list[tuple[str, str]] = []
        remaining = keywords
        for _ in range(self.T):
            messages = TQ.build_conversation_for_next_question(keywords, history)
            question = _generate_text(self.loaded, messages, max_new_tokens=40)
            partition_text = _generate_text(
                self.loaded, TQ.build_partition_prompt(question, remaining), max_new_tokens=600
            )
            yes_set, no_set = TQ.parse_partition(partition_text, remaining)
            answer = "Yes" if secret in yes_set else "No"
            history.append((question, answer))
            remaining = yes_set if secret in yes_set else no_set
        return Game(keywords=keywords, secret=secret, T=self.T, history=history)

    def _load_checkpoint(self) -> list[Game]:
        if not (self.checkpoint_path and self.checkpoint_path.exists()):
            return []
        return [self._seed_from_dict(blob) for blob in json.loads(self.checkpoint_path.read_text())]

    def _save_checkpoint(self) -> None:
        if self.checkpoint_path:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_path.write_text(json.dumps([asdict(g) for g in self.seeds], indent=1))

    def generate(self) -> None:
        self.seeds = self._load_checkpoint()
        stale = any(len(g.keywords) != self.k or g.T != self.T for g in self.seeds)
        if stale:
            print(
                f"[TwentyQuestionsDataset] checkpoint at {self.checkpoint_path} was written with "
                f"different (k, T) settings -- discarding it and replaying from scratch"
            )
            self.seeds = []

        target = len(CATEGORY) * self.n_games
        already = len(self.seeds)
        if already >= target:
            print(f"[TwentyQuestionsDataset] loaded {target} already-played games from checkpoint")
            self.seeds = self.seeds[:target]
            return
        if already:
            print(f"[TwentyQuestionsDataset] resuming from checkpoint: {already}/{target} games already played")

        index = 0
        for category in CATEGORY:
            for _ in range(self.n_games):
                if index < already:
                    index += 1
                    continue
                # Seeded by (rng_seed, index), not a shared mutable RNG stream, so a
                # resumed run draws exactly the same (keywords, secret) a
                # from-scratch run would have at this index -- independent of
                # where the resume actually starts.
                draw_rng = np.random.default_rng((self.rng_seed, index))
                keywords = sample(category, self.k, seed=int(draw_rng.integers(0, 2**31)))
                secret = keywords[int(draw_rng.integers(0, len(keywords)))]
                self.seeds.append(self._play_one_game(keywords, secret))
                self._save_checkpoint()
                index += 1
                print(f"[TwentyQuestionsDataset] played {index}/{target} games ({category})")

    def inquiry(self, seed: Game) -> Inquiry:
        return Inquiry(
            f"You are playing 20 Questions. The keyword universe is: "
            f"{', '.join(seed.keywords)}.\n{seed.history_str()}\nWhat is your next Yes/No question?",
            0.7,
            None,
        )


# --------------------------------------------------------------------------- #
# Download: TriviaQA
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TriviaQASeed:
    trivia_question: str
    answer: str


class TriviaQA(Dataset):
    """`generate()` downloads-and-loads: `data.load_triviaqa` already handles both
    (raising if the on-disk copy from §2.3.1's setup script is missing)."""

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
            self.seeds.append(TriviaQASeed(item.question, answer))

    def inquiry(self, seed: TriviaQASeed) -> Inquiry:
        return Inquiry(self.raw_question(seed.trivia_question, seed.answer), 0.7, None)
