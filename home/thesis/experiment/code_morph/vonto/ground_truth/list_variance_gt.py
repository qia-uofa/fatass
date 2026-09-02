"""List variance: how spread out the model's own generated list of items is
in word2vec embedding space — computed counterpart to
`observation_method.VarietyOM`'s self-report."""

from __future__ import annotations

import numpy as np

from ..dataset import Trial, download_word2vec_vectors, load_word2vec_vectors, parse_list_response
from .ground_truth import GroundTruth


class ListVarianceGT(GroundTruth):
    """Only meaningful for a list-shaped response (`ListElicitationDataset`):
    parses ``trial.response`` into its individual items
    (`vonto.dataset.parse_list_response`), embeds each with word2vec (a
    multi-word item tries its underscore-joined phrase form first, e.g.
    ``coffee_table``, then falls back to averaging its constituent words'
    own vectors — GoogleNews word2vec's vocabulary joins common phrases with
    underscores, never spaces, so a raw ``"coffee table"`` lookup would
    otherwise just silently miss), and scores the list by its own mean
    pairwise cosine *distance* (0 = every item points the same direction, 2 =
    every pair is diametrically opposed), rescaled by ``/ 2`` into
    ``[0, 1]``. Absolute per trial — it never compares one trial's list
    against another's — but ``values`` still does the vector lookup for the
    whole batch in one streaming pass over the (multi-gigabyte) word2vec
    file, rather than reopening it per trial.
    """

    name = "list_variance"
    tags = ["baseline", "narrow", "varied"]

    def values(self, trials: list[Trial]) -> list[float]:
        parsed = [parse_list_response(t.response) for t in trials]

        # A multi-word item (e.g. "coffee table") is never itself a word2vec
        # key -- the vocabulary joins common phrases with underscores instead
        # ("coffee_table") -- so ask for both that joined form and each
        # constituent word up front, in the same streaming pass, rather than
        # silently dropping every multi-word item down to `len(vecs) < 2`.
        wanted: set[str] = set()
        for items in parsed:
            for item in items:
                words = item.lower().split()
                wanted.add("_".join(words))
                wanted.update(words)
        vectors = load_word2vec_vectors(download_word2vec_vectors(), wanted) if wanted else {}

        def embed(item: str) -> np.ndarray | None:
            words = item.lower().split()
            phrase = "_".join(words)
            if phrase in vectors:
                return vectors[phrase]
            word_vecs = [vectors[w] for w in words if w in vectors]
            return np.mean(word_vecs, axis=0) if word_vecs else None

        out = []
        for items in parsed:
            vecs = [v for v in (embed(item) for item in items) if v is not None]
            if len(vecs) < 2:
                out.append(0.0)
                continue
            matrix = np.stack(vecs)
            normalized = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
            cosine_sim = normalized @ normalized.T
            i, j = np.triu_indices(len(vecs), k=1)
            mean_distance = float(np.mean(1.0 - cosine_sim[i, j]))
            out.append(min(max(mean_distance / 2.0, 0.0), 1.0))
        return out
