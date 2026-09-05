"""Synonyms: word pairs at three relation tiers, drawn directly from human-
annotated lexical-relation benchmarks — see `SynonymsDataset`'s docstring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .dataset import Dataset, Inquiry


def _lexical_relation_pairs(dataset: str, split: str) -> list[tuple[str, str, str]]:
    """``(head, tail, relation)`` triples from one split of
    `relbert/lexical_relation_classification` — five human-annotated lexical-
    relation benchmarks (EVALution, CogALexV, K&H+N, BLESS, ROOT09), each a
    small JSONL file."""
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


def download_word2vec_vectors() -> Path:
    """Fetch the raw (non-gensim) GoogleNews word2vec binary via `huggingface_hub`."""
    from huggingface_hub import hf_hub_download

    return Path(
        hf_hub_download(
            repo_id="NathaNn1111/word2vec-google-news-negative-300-bin",
            filename="GoogleNews-vectors-negative300.bin",
        )
    )


def load_word2vec_vectors(path: str | Path, wanted: set[str]) -> dict[str, np.ndarray]:
    """Read only ``wanted`` words' vectors out of a raw word2vec ``.bin`` file in
    one streaming pass (case-insensitive) — the classic binary format: an ASCII
    header line ``"vocab_size dim"``, then per word, a space-terminated ASCII
    token followed by ``dim`` raw float32 bytes. Not gensim: gensim's compiled
    extensions don't build on every environment this runs in, so this
    reimplements just the read path needed here, in plain numpy, against the
    original file format.
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


@dataclass(frozen=True)
class SynonymSeed:
    wordpair: tuple[str, str]
    relation: str  # "twin" | "sibling" | "relative"

    @property
    def answer(self) -> str:
        """The correct Yes/No answer to `SynonymsDataset.inquiry`'s own
        question — only "twin" pairs genuinely mean the same thing; "sibling"
        and "relative" pairs are related but distinct. Exposed the same way
        every other seed's reference answer is (a plain ``answer`` field/
        property), so `ground_truth.CorrectnessGT`/`ChallengeGT` need no
        per-dataset special-casing to grade this dataset too.
        """
        return "Yes" if self.relation == "twin" else "No"


class SynonymsDataset(Dataset):
    """``n`` word pairs per relation tier, drawn directly from human-annotated
    lexical-relation benchmarks — not a sampled keyword paired with a
    procedurally generated related word. Pairs need not share any word across
    tiers: equal pairs, not one keyword's three relations.

    - **twin** (interchangeable) — EVALution's ``"Synonym"`` + CogALexV's
      ``"SYN"`` pairs, human-annotated, filtered to require word2vec cosine
      similarity >= ``min_twin_similarity`` (a labeled "Synonym" pair isn't
      automatically interchangeable in every context — this rejects the
      loosest of the labeled pairs).
    - **sibling** (same meaning, not interchangeable) — K&H+N's ``"sibl"``
      pairs: an established co-hyponym relation (two words sharing an
      immediate parent category, e.g. "cat"/"dog" under "mammal").
    - **relative** (similar meaning) — BLESS's ``hyper``/``mero``/``attri``/
      ``event`` pairs (excluding BLESS's own ``coord``, the same co-hyponym
      relation as "sibling", and ``random``, unrelated): genuinely related,
      but neither synonymous nor co-hyponyms.
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
            {(h, t) for h, t, r in _lexical_relation_pairs("EVALution", "train") if r == "Synonym"}
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
        # temperature=0 -- greedy, matching the paper's own "greedy decoding,
        # temperature = 0" requirement (reproduction guidebook §2.1, §2.2)
        # for the calibration datasets this feeds; `generate_trial` now
        # actually samples at whatever temperature it's given, so this can no
        # longer be a nonzero placeholder the way it used to be before that
        # was wired up.
        #
        # "Answer with only 'Yes' or 'No'" (same forced-choice phrasing
        # `ground_truth.challenge_gt._CHALLENGE_QUESTION` uses elsewhere) --
        # without it the model reliably hedges with a multi-sentence
        # explanation ("can sometimes be used interchangeably, but there are
        # subtle differences...") rather than a clean verdict, which is what
        # actually made `CorrectnessGT`'s alias-substring match against
        # "Yes"/"No" unreliable, not the substring check itself.
        return Inquiry(f'Do "{a}" and "{b}" mean the same thing? Answer with only "Yes" or "No".', 0.0, 0)
