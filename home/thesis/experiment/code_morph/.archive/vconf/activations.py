"""Activation collection and caching (§2.10, §15.3).

The 3,000-trial activation-collection set is run once with capture hooks and
stored to disk in float16; steering vectors (§4.2), probes (§9), the natural
variability statistics (§8) and every patch/swap donor read from this store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

from . import config as cfg
from .hooks import capture_positions
from .models import LoadedModel, pad_batch
from .positions import RenderedPrompt


@dataclass
class ActivationStore:
    """Residual-stream activations indexed by ``(layer, position)``."""

    layers: tuple[int, ...]
    positions: tuple[str, ...]
    data: dict[tuple[int, str], np.ndarray] = field(default_factory=dict)
    trial_ids: list[str] = field(default_factory=list)

    def get(self, layer: int, position: str) -> np.ndarray:
        """``(n_trials, d_model)`` float32 activations."""
        return self.data[(layer, position)].astype(np.float32)

    def tensor(self, layer: int, position: str, device=None, dtype=torch.float32) -> torch.Tensor:
        return torch.tensor(self.get(layer, position), dtype=dtype, device=device)

    def mean(self, layer: int, position: str, index: np.ndarray | None = None) -> np.ndarray:
        acts = self.get(layer, position)
        return (acts if index is None else acts[index]).mean(axis=0)

    def norms(self, layer: int, position: str) -> np.ndarray:
        """L2 norms of the residual stream — the basis of the 3% scaling (§4.2, §13 #5)."""
        return np.linalg.norm(self.get(layer, position), axis=-1)

    def subset(self, index: np.ndarray) -> "ActivationStore":
        return ActivationStore(
            layers=self.layers,
            positions=self.positions,
            data={key: value[index] for key, value in self.data.items()},
            trial_ids=[self.trial_ids[i] for i in np.atleast_1d(index)] if self.trial_ids else [],
        )

    def save(self, path: Path) -> Path:
        """Write the store atomically, so a concurrent reader never sees a partial file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp.npz")
        np.savez_compressed(
            temporary,
            layers=np.array(self.layers),
            positions=np.array(self.positions, dtype=object),
            trial_ids=np.array(self.trial_ids, dtype=object),
            **{f"{layer}|{position}": value for (layer, position), value in self.data.items()},
        )
        os.replace(temporary, path)
        return path

    @classmethod
    def load(cls, path: Path) -> "ActivationStore":
        blob = np.load(Path(path), allow_pickle=True)
        data = {}
        for key in blob.files:
            if "|" not in key:
                continue
            layer, position = key.split("|", 1)
            data[(int(layer), position)] = blob[key]
        return cls(
            layers=tuple(int(x) for x in blob["layers"]),
            positions=tuple(str(x) for x in blob["positions"]),
            data=data,
            trial_ids=[str(x) for x in blob["trial_ids"]],
        )


@torch.no_grad()
def collect_activations(
    loaded: LoadedModel,
    rendered: list[RenderedPrompt],
    layers: tuple[int, ...],
    positions: tuple[str, ...],
    trial_ids: list[str] | None = None,
    batch_size: int | None = None,
    progress=None,
) -> ActivationStore:
    """Run clean forward passes with capture hooks and store the activations (§2.10)."""
    batch_size = batch_size or loaded.config.batch_size
    store = ActivationStore(layers=tuple(layers), positions=tuple(positions))
    collected: dict[tuple[int, str], list[np.ndarray]] = {
        (layer, position): [] for layer in layers for position in positions
    }
    batches = range(0, len(rendered), batch_size)
    iterator = progress(batches) if progress else batches
    for start in iterator:
        chunk = rendered[start: start + batch_size]
        pos_matrix = [[r.positions[p] for p in positions] for r in chunk]
        input_ids, attention_mask, _ = pad_batch(
            chunk, loaded.tokenizer.pad_token_id, loaded.device
        )
        captured: dict[int, torch.Tensor] = {}
        with capture_positions(loaded.model, layers, captured, pos_matrix):
            loaded.model(input_ids=input_ids, attention_mask=attention_mask)
        for layer in layers:
            rows = captured[layer].numpy()
            for j, position in enumerate(positions):
                collected[(layer, position)].append(rows[:, j, :])
    store.data = {key: np.concatenate(value, axis=0) for key, value in collected.items()}
    store.trial_ids = list(trial_ids or [])
    return store


def activation_path(name: str, directory: Path | None = None) -> Path:
    directory = Path(directory or cfg.ACTIVATIONS_DIR)
    return directory / f"{name}.npz"


# --------------------------------------------------------------------------- #
# List elicitation (plan_benzon.md Part 4) — pooling an arbitrary text span
# parsed back out of a generation, not read live during the forward pass that
# produced it (unlike `collect_activations`, which captures fixed prompt
# positions during the pass that generates them).
# --------------------------------------------------------------------------- #


@torch.no_grad()
def pooled_hidden_state(loaded: LoadedModel, text: str, layer: int | None = None) -> np.ndarray:
    """Mean-pooled hidden state of ``text``, encoded standalone.

    No external embedding model exists anywhere in this repo, and none is
    needed: the loaded model's *own* hidden states are the natural embedding
    source, consistent with how every other intervention here already reads
    that model's own activations rather than an external tool's. ``text`` is
    encoded on its own (no chat template, no surrounding prompt) — it's an
    item already parsed back out of a completed generation
    (`prompts.parse_list_items`), not a live position inside the prompt that
    produced it, so there's no original forward pass to hook into.

    ``layer`` defaults to the last decoder layer (the model's own most
    semantically-composed representation, mirroring how every other
    intervention in this repo reads the *final* residual stream unless a
    specific earlier layer is under study); pass an explicit 0-indexed layer
    to pool an earlier one instead.
    """
    device = next(loaded.model.parameters()).device
    enc = loaded.tokenizer(text, return_tensors="pt", add_special_tokens=False).to(device)
    out = loaded.model(**enc, output_hidden_states=True)
    # hidden_states[0] is the embedding layer's output; hidden_states[i + 1] is
    # decoder layer i's — so plain -1 already selects the last decoder layer.
    hidden = out.hidden_states[-1 if layer is None else layer + 1][0]
    return hidden.float().mean(dim=0).cpu().numpy()


def list_embedding_variety(trial, loaded: LoadedModel) -> float:
    """`variety`'s ground truth (plan_benzon.md Part 4): mean pairwise cosine
    distance between a generated list's own parsed items' pooled hidden
    states. Signature note: like `metrics.answer_set_entropy`, this needs
    more than just ``trial`` — bind ``loaded`` with ``functools.partial`` at
    the point the run's model is actually loaded, not as a bare module
    constant (plan_benzon.md wrinkle 2).
    """
    from .metrics import mean_pairwise_cosine_distance  # deferred: avoids a cycle with metrics<->activations
    from .prompts import parse_list_items

    items = parse_list_items(trial.answer)
    vectors = [pooled_hidden_state(loaded, item) for item in items]
    return mean_pairwise_cosine_distance(vectors)
