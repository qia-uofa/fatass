"""List elicitation: one seed per sampled keyword, no model call at
generation time — see `ListElicitationDataset`'s docstring."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .dataset import CATEGORY, Dataset, Inquiry, sample


def parse_list_response(response: str) -> list[str]:
    """Split a model's free-text answer to a "give me a list of ..." prompt
    into its individual items — one per line if it answered with multiple
    lines (stripping any leading numbering/bullet, e.g. ``"1. "``/``"- "``),
    else comma/semicolon-separated. Used by `ground_truth.ListVarianceGT` to
    grade the list itself, not just the free-text response as a whole.
    """
    lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
    if len(lines) <= 1:
        lines = [item.strip() for item in re.split(r"[,;]", response) if item.strip()]
    items = []
    for line in lines:
        # Only an actual numbering/bullet marker (e.g. "1. ", "2) ", "- ",
        # "* "), never a bare leading char class -- that used to strip the
        # leading digit off a genuine item like "3D printer", mangling it
        # into "D printer".
        cleaned = re.sub(r"^(?:\d+[.)]|[-*])\s*", "", line).strip()
        if cleaned:
            items.append(cleaned)
    return items


@dataclass(frozen=True)
class ListElicitationSeed:
    keyword: str
    temperature: float
    generation_seed: int


class ListElicitationDataset(Dataset):
    """``T`` seeds per sampled keyword, each its own random sampling
    temperature (uniform in ``[0, 0.8)``) and generation seed — not a chosen
    list of items, and not just one temperature per keyword: the actual list
    only comes into existence later, when `inquiry(seed)`'s prompt is
    actually sent to a model. Multiple temperatures per keyword is what lets
    a temperature-vs-variety correlation be computed *within* a keyword
    (controlling for the keyword's own inherent variance) rather than only
    pooled across keywords, where each keyword contributing just one
    temperature confounds the two.
    """

    seed_cls = ListElicitationSeed

    def shape_params(self) -> dict[str, object]:
        return {"n": self.n, "k": self.k, "T": self.T}

    def __init__(self, n: int, k: int, T: int, rng_seed: int = 0) -> None:
        super().__init__()
        self.n, self.k, self.T = n, k, T
        self._rng = np.random.default_rng(rng_seed)

    def generate(self) -> None:
        for category in CATEGORY:
            for keyword in sample(category, self.n):
                for _ in range(self.T):
                    temperature = float(self._rng.uniform(0.0, 0.8))
                    generation_seed = int(self._rng.integers(0, 2**31))
                    self.seeds.append(ListElicitationSeed(keyword, temperature, generation_seed))

    def inquiry(self, seed: ListElicitationSeed) -> Inquiry:
        # stop_strings=None -- `Inquiry`'s own default (a blank line ends
        # generation) assumes a short factual answer; a k-item list needs the
        # model to write many lines, almost certainly separated by at least
        # one blank line (the paragraph break after the intro sentence, if
        # nothing else), so that default would stop generation before the
        # list itself ever appears. Verified directly: with the default
        # still in place, 188/200 real trials ended right at the intro
        # sentence's colon, 0 list items generated.
        return Inquiry(
            f"Give me a list of {self.k} things, starting with {seed.keyword}.",
            seed.temperature,
            seed.generation_seed,
            stop_strings=None,
        )
