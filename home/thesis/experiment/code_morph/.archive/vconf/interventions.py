"""The shared machinery every causal experiment reuses (§2.10).

One function runs a batch of trials with one residual-stream intervention at one
(layer, position) and returns the class logits; :func:`intervention_metrics`
turns clean and intervened logits into the three metrics of §2.8.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import torch

from . import metrics as M
from .hooks import residual_intervention
from .models import LoadedModel, pad_batch
from .positions import RenderedPrompt


@torch.no_grad()
def run_with_intervention(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    layer: int,
    fn_factory: Callable[[list[RenderedPrompt], slice], Callable] | None,
    target_ids: list[int],
    batch_size: int | None = None,
    inputs_embeds_factory: Callable[[list[RenderedPrompt], torch.Tensor], torch.Tensor] | None = None,
) -> np.ndarray:
    """Forward passes with one intervention at one layer; returns ``(n, K)`` class logits.

    ``fn_factory(chunk, offset)`` builds the residual-stream function for a
    batch (``None`` runs the clean pass).  ``inputs_embeds_factory`` optionally
    replaces the input embeddings, which is how patching corrupts the answer
    tokens before layer 0 (§5.2).
    """
    batch_size = batch_size or loaded.config.batch_size
    out: list[np.ndarray] = []
    for start in range(0, len(rendered), batch_size):
        chunk = rendered[start: start + batch_size]
        input_ids, attention_mask, lengths = pad_batch(
            chunk, loaded.tokenizer.pad_token_id, loaded.device
        )
        kwargs = {"attention_mask": attention_mask}
        if inputs_embeds_factory is not None:
            kwargs["inputs_embeds"] = inputs_embeds_factory(chunk, input_ids)
        else:
            kwargs["input_ids"] = input_ids
        fn = fn_factory(chunk, start) if fn_factory is not None else None
        if fn is None:
            logits = loaded.model(**kwargs).logits
        else:
            with residual_intervention(loaded.model, layer, fn):
                logits = loaded.model(**kwargs).logits
        idx = torch.tensor([n - 1 for n in lengths], device=logits.device)
        final = logits[torch.arange(len(chunk), device=logits.device), idx, :].float()
        out.append(final[:, target_ids].cpu().numpy())
    return np.concatenate(out, axis=0)


def compute_clean_logits(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    target_ids: list[int],
    batch_size: int | None = None,
) -> np.ndarray:
    """Clean ``(n, K)`` class logits computed with the *same* batching as the runs.

    bf16 attention is not bit-exact across batch compositions, and the metrics of
    §2.8 compare an intervened run against its clean baseline token-by-token, so
    the baseline is recomputed over exactly the batch layout the intervention
    runs use rather than reused from a differently batched pass.
    """
    return run_with_intervention(loaded, rendered, 0, None, target_ids, batch_size)


def intervention_metrics(
    intervened_logits: np.ndarray,
    clean_logits: np.ndarray,
    clean_index: np.ndarray,
    midpoints: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Per-trial values of the three metrics of §2.8, relative to the clean run."""
    intervened_index = M.predicted_class(intervened_logits)
    return {
        "clean_index": np.asarray(clean_index, dtype=int),
        "intervened_index": intervened_index,
        "clean_logit_diff": M.logit_difference(clean_logits, clean_index),
        "intervened_logit_diff": M.logit_difference(intervened_logits, clean_index),
        "logit_diff_change": M.logit_difference_change(
            intervened_logits, clean_logits, clean_index
        ),
        "clean_confidence": M.confidence(clean_index, midpoints),
        "intervened_confidence": M.confidence(intervened_index, midpoints),
        "confidence_change": M.confidence_change(intervened_index, clean_index, midpoints),
        "token_changed": (intervened_index != np.asarray(clean_index, dtype=int)).astype(float),
    }


def numeric_midpoints(prompt_kind: str) -> np.ndarray | None:
    """The value each of the K target tokens stands for.

    Categorical prompts use the class midpoints (§2.5.1); the numeric prompts'
    first-token metrics are over the ten digits, whose "confidence" is the digit
    itself (0–9 for the minimal prompt, the leading digit for 0–100).
    """
    if prompt_kind in ("categorical", "magistral"):
        return None
    return np.arange(10, dtype=float)
