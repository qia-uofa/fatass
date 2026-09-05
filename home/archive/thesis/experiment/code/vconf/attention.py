"""Attention knockout for Experiment 8 (§11).

For a source position ``s`` and target position ``t``, the attention weight
``α_{t←s}`` is set to zero **across all heads** within a window of consecutive
layers, by adding ``−inf`` to the pre-softmax attention scores at the ``(t, s)``
entries.  ``attn_implementation="eager"`` is required so the attention
probabilities are materialised and hookable (§11.1).
"""

from __future__ import annotations

from contextlib import contextmanager

import torch

from .models import layers_of
from .positions import RenderedPrompt

#: The pathways the paper blocks (§11.4 minimal prompt, §11.5 categorical prompt).
MINIMAL_PATHWAYS = ("CC->Q+A", "CC->PANL", "CC->PANL+1", "PANL->A", "PANL->last_A")
CATEGORICAL_PATHWAYS = (
    "CC->NL+1", "CC->NL", "CC->A", "CC->Q", "CC->Q+A",
    "ALL->NL", "ALL->last_A", "ALL->NL+last_A", "ALL->last_A_keepNL",
    "ALL->A", "ALL->NL+A", "ALL->A_keepNL",
)


def window_layers(center: int, n_layers: int, window: int = 12) -> list[int]:
    """The 12 consecutive layers centred at ``center`` (§11.2).

    A point plotted at layer 30 means attention was blocked across layers 24–35.
    """
    lo = max(0, center - window // 2)
    hi = min(n_layers, center + window - window // 2)
    return list(range(lo, hi))


def _source_positions(rendered: RenderedPrompt, spec: str) -> list[int]:
    """Token indices named by a source spec such as ``Q+A`` or ``NL+last_A``."""
    pos = rendered.positions
    answer_span = list(range(pos["first A"], pos["last A"] + 1))
    question_span = list(range(*_question_token_range(rendered)))
    # "NL+1" / "PANL+1" name the control position, not a sum of two specs.
    if spec.strip() in ("NL+1", "PANL+1"):
        return [pos["PANL+1"]]
    out: list[int] = []
    for part in spec.split("+"):
        part = part.strip()
        if part in ("NL", "PANL"):
            out.append(pos["PANL"])
        elif part == "A":
            out.extend(answer_span)
        elif part == "last_A":
            out.append(pos["last A"])
        elif part == "Q":
            out.extend(question_span)
        elif part == "CC":
            out.append(pos["CC"])
        else:
            raise KeyError(f"unknown source spec part: {part!r}")
    return sorted(set(out))


def _question_token_range(rendered: RenderedPrompt) -> tuple[int, int]:
    from .positions import span_to_tokens

    first, last = span_to_tokens(rendered.offsets, rendered.spans["question"])
    return first, last + 1


def parse_pathway(name: str) -> tuple[str, str, bool]:
    """``"ALL->A_keepNL"`` → ``("ALL", "A", True)``."""
    target, _, source = name.partition("->")
    keep_nl = source.endswith("_keepNL")
    if keep_nl:
        source = source[: -len("_keepNL")]
    return target.strip(), source.strip(), keep_nl


def pathway_edges(rendered: RenderedPrompt, name: str) -> list[tuple[int, int]]:
    """``(target, source)`` token-index pairs to block for a named pathway (§11.4/§11.5).

    ``CC->…`` blocks only the final position's attention; ``PANL->…`` only
    PANL's; ``ALL->…`` blocks every token downstream of the sources.  The
    ``_keepNL`` variants exempt PANL from the block, which is the dissociation
    the paper relies on.
    """
    target_spec, source_spec, keep_nl = parse_pathway(name)
    sources = _source_positions(rendered, source_spec)
    if target_spec == "CC":
        targets = [rendered.positions["CC"]]
    elif target_spec in ("PANL", "NL"):
        targets = [rendered.positions["PANL"]]
    elif target_spec == "ALL":
        first_downstream = max(sources) + 1
        targets = [t for t in range(first_downstream, rendered.n_tokens) if t not in sources]
    else:
        raise KeyError(f"unknown target spec: {target_spec!r}")
    if keep_nl:
        targets = [t for t in targets if t != rendered.positions["PANL"]]
    return [(t, s) for t in targets for s in sources if s < t]


def build_block_mask(
    edges_per_trial: list[list[tuple[int, int]]],
    seq_len: int,
    device,
    dtype,
) -> torch.Tensor:
    """Additive ``(batch, 1, q_len, kv_len)`` mask with ``−inf`` on blocked edges (§11.1)."""
    mask = torch.zeros(len(edges_per_trial), 1, seq_len, seq_len, device=device, dtype=dtype)
    neg_inf = torch.finfo(dtype).min
    for i, edges in enumerate(edges_per_trial):
        for target, source in edges:
            mask[i, 0, target, source] = neg_inf
    return mask


def causal_mask(
    attention_mask_2d: torch.Tensor, dtype: torch.dtype
) -> torch.Tensor:
    """A ``(batch, 1, seq, seq)`` additive causal + padding mask, as a fallback.

    Used when the model does not hand its decoder layers a 4-D float mask.
    """
    batch, seq = attention_mask_2d.shape
    device = attention_mask_2d.device
    neg_inf = torch.finfo(dtype).min
    causal = torch.full((seq, seq), neg_inf, device=device, dtype=dtype).triu(1)
    mask = causal.unsqueeze(0).unsqueeze(0).expand(batch, 1, seq, seq).clone()
    pad = (attention_mask_2d == 0).unsqueeze(1).unsqueeze(2)
    return mask.masked_fill(pad, neg_inf)


@contextmanager
def attention_knockout(model, layer_indices, block_mask: torch.Tensor, attention_mask_2d=None):
    """Block the given edges across all heads, for the given layers only (§11.1/§11.2).

    Registers a pre-hook on each decoder layer in the window that adds the
    ``−inf`` block mask to the additive attention mask that layer receives;
    layers outside the window are left untouched.
    """
    handles = []

    def hook(module, args, kwargs):
        mask = kwargs.get("attention_mask")
        if isinstance(mask, dict):  # transformers may pass one mask per attention type
            kwargs["attention_mask"] = {
                key: (value + block_mask.to(value.dtype)) if torch.is_tensor(value) and value.dim() == 4 else value
                for key, value in mask.items()
            }
            return args, kwargs
        if torch.is_tensor(mask) and mask.dim() == 4:
            kwargs["attention_mask"] = mask + block_mask.to(mask.dtype)
        else:
            if attention_mask_2d is None:
                raise ValueError(
                    "the decoder layer received no 4-D attention mask; pass "
                    "attention_mask_2d so a causal mask can be built"
                )
            base = causal_mask(attention_mask_2d, block_mask.dtype)
            kwargs["attention_mask"] = base + block_mask.to(base.dtype)
        return args, kwargs

    try:
        for layer_idx in layer_indices:
            handles.append(
                layers_of(model)[layer_idx].register_forward_pre_hook(hook, with_kwargs=True)
            )
        yield
    finally:
        for handle in handles:
            handle.remove()


@torch.no_grad()
def verify_blocked(
    model, input_ids, attention_mask, layer_indices, block_mask, edges
) -> float:
    """Assert post-softmax attention from ``t`` to ``s`` is zero in a blocked layer (§11.1).

    Returns the maximum blocked attention probability found (should be 0.0).
    """
    with attention_knockout(model, layer_indices, block_mask, attention_mask):
        out = model(
            input_ids=input_ids, attention_mask=attention_mask, output_attentions=True
        )
    worst = 0.0
    for layer_idx in layer_indices:
        attn = out.attentions[layer_idx]  # (batch, heads, q, kv)
        for i, trial_edges in enumerate(edges):
            for target, source in trial_edges:
                worst = max(worst, float(attn[i, :, target, source].max()))
    return worst
