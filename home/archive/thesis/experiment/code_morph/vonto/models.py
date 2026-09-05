"""Minimal model loading for vonto — just enough to run a chat-style LLM for
game-play generation (`dataset.TwentyQuestionsDataset`). Not a port of
vconf's own `models.py` (no prompt-position machinery, no class-token logits
— vonto doesn't need those for dataset preparation)."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from . import config as cfg


@dataclass
class LoadedModel:
    """A checkpoint plus its tokenizer."""

    model: torch.nn.Module
    tokenizer: object

    @property
    def device(self) -> torch.device:
        return next(self.model.parameters()).device


def load_model(model_key: str = "qwen", dtype: str = "bfloat16") -> LoadedModel:
    """Load a chat checkpoint in bf16, eval mode, gradients disabled."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg.load_credentials()
    checkpoint = cfg.MODELS[model_key]
    torch.set_grad_enabled(False)
    model = AutoModelForCausalLM.from_pretrained(checkpoint, dtype=getattr(torch, dtype))
    model = model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return LoadedModel(model=model, tokenizer=tokenizer)
