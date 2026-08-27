"""Residual-stream hook infrastructure shared by every intervention (§2.10).

All four activation interventions — steer / patch / noise / swap — are the same
operation: modify the residual stream at **one token position** at **one layer**,
applied at the *output of the decoder layer* (i.e. after that layer's MLP
block, §2.10 / §13 #4).  Corruption for patching is different: it happens at the
input-embedding level so it propagates through the whole forward pass (§5.2).
"""

from __future__ import annotations

from contextlib import contextmanager

import torch

from .models import layers_of


def _as_positions(pos, batch: int) -> list[int]:
    """Broadcast a scalar position, or validate a per-trial list of positions."""
    if isinstance(pos, int):
        return [pos] * batch
    positions = list(pos)
    if len(positions) != batch:
        raise ValueError(f"expected {batch} positions, got {len(positions)}")
    return positions


def _as_vectors(vec: torch.Tensor, batch: int) -> torch.Tensor:
    """Broadcast a single ``(d,)`` vector to ``(batch, d)`` or validate a batch."""
    if vec.dim() == 1:
        return vec.unsqueeze(0).expand(batch, -1)
    if vec.shape[0] != batch:
        raise ValueError(f"expected {batch} vectors, got {vec.shape[0]}")
    return vec


@contextmanager
def residual_intervention(model, layer_idx: int, fn):
    """``fn(hidden_states) -> hidden_states`` on the output of decoder layer ``layer_idx``."""

    def hook(module, args, output):
        if isinstance(output, tuple):
            return (fn(output[0]),) + output[1:]
        return fn(output)

    handle = layers_of(model)[layer_idx].register_forward_hook(hook)
    try:
        yield
    finally:
        handle.remove()


# --------------------------------------------------------------------------- #
# The four interventions, all as `fn` factories (§2.10)
# --------------------------------------------------------------------------- #


def steer(pos, vec: torch.Tensor, alpha: float):
    """Additive steering at one position: ``h[pos] += alpha * v`` (§4.3)."""

    def fn(hs: torch.Tensor) -> torch.Tensor:
        hs = hs.clone()
        positions = _as_positions(pos, hs.shape[0])
        vectors = _as_vectors(vec.to(hs.dtype).to(hs.device), hs.shape[0])
        for i, p in enumerate(positions):
            hs[i, p, :] = hs[i, p, :] + alpha * vectors[i]
        return hs

    return fn


def replace(pos, new_vec: torch.Tensor):
    """Direct replacement at one position — used for noising and swapping (§2.10)."""

    def fn(hs: torch.Tensor) -> torch.Tensor:
        hs = hs.clone()
        positions = _as_positions(pos, hs.shape[0])
        vectors = _as_vectors(new_vec.to(hs.dtype).to(hs.device), hs.shape[0])
        for i, p in enumerate(positions):
            hs[i, p, :] = vectors[i]
        return hs

    return fn


def patch(pos, clean_vec: torch.Tensor):
    """Identical mechanics to :func:`replace`; the semantics differ (§5.3)."""
    return replace(pos, clean_vec)


# --------------------------------------------------------------------------- #
# Capturing clean activations (§2.10 "Caching clean activations")
# --------------------------------------------------------------------------- #


@contextmanager
def capture_residual(model, layer_indices, store: dict, positions=None):
    """Capture residual-stream activations at the output of the given layers.

    ``positions`` may be ``None`` (store the full sequence) or a list of
    per-trial token indices, in which case only those rows are kept — the shape
    stored is then ``(batch, d_model)``.  Everything is detached to CPU float16,
    as §2.10 recommends.
    """
    handles = []

    def make_hook(layer_idx):
        def hook(module, args, output):
            hs = output[0] if isinstance(output, tuple) else output
            if positions is None:
                store[layer_idx] = hs.detach().to("cpu", torch.float16)
            else:
                pos = _as_positions(positions, hs.shape[0])
                rows = torch.stack([hs[i, p, :] for i, p in enumerate(pos)])
                store[layer_idx] = rows.detach().to("cpu", torch.float16)

        return hook

    try:
        for layer_idx in layer_indices:
            handles.append(layers_of(model)[layer_idx].register_forward_hook(make_hook(layer_idx)))
        yield store
    finally:
        for handle in handles:
            handle.remove()


@torch.no_grad()
def residual_norms(model, layer_indices, input_ids, attention_mask, positions) -> dict[int, torch.Tensor]:
    """Mean L2 norm of the residual stream at each (layer, position) (§13 #5)."""
    store: dict[int, torch.Tensor] = {}
    with capture_residual(model, layer_indices, store, positions=positions):
        model(input_ids=input_ids, attention_mask=attention_mask)
    return {layer: acts.float().norm(dim=-1) for layer, acts in store.items()}


# --------------------------------------------------------------------------- #
# Embedding-level corruption (patching only, §5.2)
# --------------------------------------------------------------------------- #


@torch.no_grad()
def input_embeddings(model, input_ids: torch.Tensor) -> torch.Tensor:
    """``(batch, seq, d)`` input embeddings, before layer 0."""
    return model.get_input_embeddings()(input_ids)


@torch.no_grad()
def corrupt_embeddings(
    embeddings: torch.Tensor, spans: list[tuple[int, int]], mean_embeddings: torch.Tensor
) -> torch.Tensor:
    """Mean-ablate the answer tokens of each trial (§5.2).

    ``spans`` gives the inclusive ``(first, last)`` answer-token span per trial;
    ``mean_embeddings`` is ``(max_answer_len, d)`` — the mean embedding *per
    answer-position index* across the calibration set, so trials with different
    answer lengths are handled position-by-position.
    """
    out = embeddings.clone()
    means = mean_embeddings.to(out.dtype).to(out.device)
    for i, (first, last) in enumerate(spans):
        for j, pos in enumerate(range(first, last + 1)):
            out[i, pos, :] = means[min(j, means.shape[0] - 1)]
    return out


def mean_answer_embeddings(
    embeddings: list[torch.Tensor], spans: list[tuple[int, int]]
) -> torch.Tensor:
    """Mean embedding per answer-position index across a calibration set (§5.2).

    ``embeddings[i]`` is the ``(seq, d)`` embedding matrix of calibration trial
    ``i``; the mean at index ``j`` averages over the calibration trials that
    have at least ``j + 1`` answer tokens.
    """
    max_len = max(last - first + 1 for first, last in spans)
    d_model = embeddings[0].shape[-1]
    device = embeddings[0].device
    totals = torch.zeros(max_len, d_model, dtype=torch.float32, device=device)
    counts = torch.zeros(max_len, dtype=torch.float32, device=device)
    for emb, (first, last) in zip(embeddings, spans):
        for j, pos in enumerate(range(first, last + 1)):
            totals[j] += emb[pos].float()
            counts[j] += 1
    counts = counts.clamp(min=1).unsqueeze(-1)
    return totals / counts


@contextmanager
def capture_positions(model, layer_indices, store: dict, pos_matrix: list[list[int]]):
    """Capture several positions per trial at once, as ``(batch, n_pos, d_model)``.

    ``pos_matrix[i]`` lists the token indices wanted for trial ``i``; only those
    rows are copied off the GPU (float16, CPU), which keeps activation
    collection over a full layer sweep affordable (§2.10, §15.3).
    """
    handles = []

    def make_hook(layer_idx):
        def hook(module, args, output):
            hs = output[0] if isinstance(output, tuple) else output
            index = torch.tensor(pos_matrix, device=hs.device, dtype=torch.long)
            rows = torch.gather(
                hs, 1, index.unsqueeze(-1).expand(-1, -1, hs.shape[-1])
            )
            store[layer_idx] = rows.detach().to("cpu", torch.float16)

        return hook

    try:
        for layer_idx in layer_indices:
            handles.append(layers_of(model)[layer_idx].register_forward_hook(make_hook(layer_idx)))
        yield store
    finally:
        for handle in handles:
            handle.remove()
