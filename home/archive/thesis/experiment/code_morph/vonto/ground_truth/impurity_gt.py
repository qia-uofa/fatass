"""Impurity: Gini impurity of the yes/no split the model's own newly
proposed 20-questions question induces over the game's keyword universe —
computed counterpart to `observation_method.ImpurityOM`'s self-report.
Exclusive to `TwentyQuestionsDataset` — unlike `VarietyOM`/`ListVarianceGT`,
which are exclusive to `ListElicitationDataset`, this one has nothing to do
with a generated list."""

from __future__ import annotations

from tqdm.auto import tqdm

from .. import twenty_questions as TQ
from ..dataset import Trial
from .ground_truth import GroundTruth


def _generate_text(loaded, prompt: str, max_new_tokens: int) -> str:
    import torch

    text = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
    )
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    with torch.no_grad():
        out = loaded.model.generate(
            **enc, max_new_tokens=max_new_tokens, do_sample=False, temperature=None, top_p=None,
            top_k=None, pad_token_id=loaded.tokenizer.pad_token_id,
        )
    new_tokens = out[:, enc["input_ids"].shape[1] :]
    return loaded.tokenizer.decode(new_tokens[0], skip_special_tokens=True).strip()


class ImpurityGT(GroundTruth):
    """Needs a loaded model (bound at construction, not a bare module-level
    constant) — classifying each candidate word Yes/No under the model's own
    newly proposed question (``trial.response`` — the real last question
    asked in the actual played game, via `Game.precomputed_response`, not a
    resynthesized one) is itself a model call
    (`vonto.twenty_questions.parse_partition`'s own partition-classification
    step, reused here as-is), not a deterministic string computation.

    Scored against the game's full ``keywords`` pool, not whatever subset
    actually remained live at this exact point in the real playthrough —
    `Game` doesn't record per-turn remaining-set snapshots, only the final
    ``(question, answer)`` history, so there's no cheaper way to recover
    "what was actually still in play here" without replaying the whole game.
    This instead measures a well-defined quantity in its own right: how
    evenly would this newly proposed question split the *whole* candidate
    universe — not identical to "how evenly does it split what's actually
    left at this turn," but the same kind of question, and the only one this
    data actually supports.

    ``0.0`` = every candidate falls on the same side (a useless yes/no
    question, tells you nothing); ``0.5`` = a perfect 50/50 split (the
    maximum possible for a two-way partition, and exactly the target
    `observation_method.ImpurityOM`'s own strategic framing asks the model to
    aim for).
    """

    name = "impurity"
    tags = ["baseline", "uneven", "even"]

    def __init__(self, loaded) -> None:
        self.loaded = loaded

    def values(self, trials: list[Trial]) -> list[float]:
        out = []
        for trial in tqdm(trials, desc="impurity: classifying candidate splits", leave=False):
            keywords = trial.seed.keywords
            n = len(keywords)
            if n == 0:
                out.append(0.0)
                continue
            partition_text = _generate_text(
                self.loaded, TQ.build_partition_prompt(trial.response, keywords), max_new_tokens=600
            )
            yes_set, no_set = TQ.parse_partition(partition_text, keywords)
            p_yes, p_no = len(yes_set) / n, len(no_set) / n
            out.append(1.0 - (p_yes**2 + p_no**2))
        return out
