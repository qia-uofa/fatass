"""Model loading, prompt rendering and the class-token machinery (§2.2, §13 #2/#3).

All computation runs on the GPU: :func:`load_model` places the checkpoint on
``cuda`` (sharding across visible devices when ``device_map="auto"``) and every
helper here moves its inputs to the model's device.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from . import config as cfgmod
from .config import RunConfig
from .positions import RenderedPrompt, cue_cut, locate_positions, remap_spans
from .prompts import CLASSES, BuiltPrompt

DTYPES = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}


def resolve_device(device: str = "cuda") -> torch.device:
    """The torch device experiments run on; CUDA is required by the setup (§2.1)."""
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available but the experiments require GPU execution "
            "(§2.1 Hardware). Check the torch build against the driver version."
        )
    return torch.device(device)


@dataclass
class LoadedModel:
    """A checkpoint plus its tokenizer and the run configuration it was loaded for."""

    model: torch.nn.Module
    tokenizer: object
    config: RunConfig

    @property
    def device(self) -> torch.device:
        return next(self.model.parameters()).device

    @property
    def n_layers(self) -> int:
        return len(layers_of(self.model))

    @property
    def d_model(self) -> int:
        return self.model.config.hidden_size


def layers_of(model) -> torch.nn.ModuleList:
    """The decoder stack — Gemma 3 / Qwen 2 / Mistral all expose it here (§2.10)."""
    inner = getattr(model, "model", model)
    inner = getattr(inner, "language_model", inner)
    return inner.layers


def load_model(cfg: RunConfig, device_map: str | None = None) -> LoadedModel:
    """Load a checkpoint in bf16, eval mode, gradients disabled (§2.2)."""
    cfgmod.load_credentials()
    device = resolve_device(cfg.device)
    torch.set_grad_enabled(False)
    kwargs = {"dtype": DTYPES[cfg.dtype]}
    if cfg.attn_implementation:
        kwargs["attn_implementation"] = cfg.attn_implementation
    if device_map is not None:
        kwargs["device_map"] = device_map
    model = AutoModelForCausalLM.from_pretrained(cfg.checkpoint, **kwargs)
    if device_map is None:
        model = model.to(device)
    model.eval()
    model.requires_grad_(False)
    tokenizer = AutoTokenizer.from_pretrained(cfg.checkpoint)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return LoadedModel(model=model, tokenizer=tokenizer, config=cfg)


# --------------------------------------------------------------------------- #
# Prompt rendering
# --------------------------------------------------------------------------- #


def render_prompt(tokenizer, built: BuiltPrompt, use_chat_template: bool = True) -> RenderedPrompt:
    """Render a built prompt into the exact string fed to the model.

    With ``use_chat_template`` (the §13 #2 default) the prompt body becomes a
    single user turn and the trailing cue (``**Confidence**:`` / ``**Answer**:``)
    is prefilled as the start of the assistant turn, so that CC (respectively
    AC) remains the very last token of the prompt.
    """
    cut = cue_cut(built)
    prefix, suffix = built.text[:cut], built.text[cut:]
    if use_chat_template:
        templated = tokenizer.apply_chat_template(
            [{"role": "user", "content": prefix}], tokenize=False, add_generation_prompt=True
        )
        head_len = templated.find(prefix)
        if head_len < 0:
            raise ValueError("chat template altered the prompt body; cannot map positions")
        text = templated + suffix
        spans = remap_spans(built.spans, cut, head_len, len(text), len(built.text))
        add_special_tokens = False
    else:
        text = built.text
        spans = dict(built.spans)
        add_special_tokens = True

    enc = tokenizer(text, add_special_tokens=add_special_tokens, return_offsets_mapping=True)
    offsets = [tuple(o) for o in enc["offset_mapping"]]
    positions = locate_positions(offsets, spans, n_tokens=len(enc["input_ids"]))
    return RenderedPrompt(
        text=text,
        input_ids=list(enc["input_ids"]),
        offsets=offsets,
        positions=positions,
        spans=spans,
        kind=built.kind,
        phase=built.phase,
    )


def panl_token(rendered: RenderedPrompt, tokenizer) -> str:
    """The decoded PANL token of a rendered prompt."""
    return tokenizer.decode([rendered.input_ids[rendered.positions["PANL"]]])


def panl_is_isolated(rendered: RenderedPrompt, tokenizer) -> bool:
    """Whether the post-answer newline is its own token in this trial (§2.6).

    Three things must hold for PANL to be the position the paper studies:

    * the token must **start** exactly at the newline that follows the answer, so
      that no answer content is merged into it (answers ending in punctuation
      otherwise produce a ``".\\n"`` token, and §14.3 lists exactly that as the
      cause of a spurious PANL/PANL+1 dissociation);
    * it must carry no word content of its own — whitespace only, which admits a
      tokenizer that merges the blank line of the numeric prompt into one
      ``"\\n\\n"`` token but rejects a merge with the following word;
    * it must not coincide with the last answer token.
    """
    index = rendered.positions["PANL"]
    token = tokenizer.decode([rendered.input_ids[index]])
    if token.strip() != "" or not token.startswith("\n"):
        return False
    if rendered.offsets[index][0] != rendered.spans["PANL"][0]:
        return False
    return rendered.positions.get("last A", -1) != index


def verify_panl_isolable(rendered: RenderedPrompt, tokenizer) -> str:
    """Assert the post-answer newline is a single, unmerged token (§2.6)."""
    token = panl_token(rendered, tokenizer)
    if not panl_is_isolated(rendered, tokenizer):
        raise ValueError(
            f"PANL is not an isolated whitespace token starting at the "
            f"post-answer newline (decoded {token!r}); the position semantics of "
            "every experiment break (§2.6)."
        )
    return token


def verify_tokenizer_panl(tokenizer, use_chat_template: bool = True) -> str:
    """Tokenizer-level check of §2.6 using a canonical short answer."""
    from .prompts import build_confidence_prompt

    built = build_confidence_prompt("Who wrote Hamlet?", "Shakespeare", "categorical")
    return verify_panl_isolable(render_prompt(tokenizer, built, use_chat_template), tokenizer)


# --------------------------------------------------------------------------- #
# Class-initial tokens (§2.5.1, §13 #3)
# --------------------------------------------------------------------------- #


def class_token_ids(tokenizer, leading_space: bool = True) -> list[int]:
    """First-token id of each of the ten confidence classes, in ``CLASSES`` order."""
    prefix = " " if leading_space else ""
    return [
        tokenizer(prefix + name, add_special_tokens=False)["input_ids"][0] for name in CLASSES
    ]


def verify_class_tokens_unique(tokenizer, leading_space: bool = True) -> list[int]:
    """Assert the ten class-initial tokens are distinct (§2.5.1)."""
    ids = class_token_ids(tokenizer, leading_space=leading_space)
    if len(set(ids)) != len(CLASSES):
        raise ValueError(
            "class-initial tokens collide — the first-token change rate and "
            "logit-difference metrics are invalid (§2.5.1)"
        )
    return ids


def digit_token_ids(tokenizer, leading_space: bool = False) -> list[int]:
    """Token ids of the digits 0–9, used as the class set for numeric prompts (§2.8)."""
    prefix = " " if leading_space else ""
    ids = [tokenizer(prefix + str(d), add_special_tokens=False)["input_ids"][0] for d in range(10)]
    if len(set(ids)) != 10:
        raise ValueError("digit-initial tokens collide — numeric metrics are invalid")
    return ids


def target_token_ids(tokenizer, prompt_kind: str, leading_space: bool = True) -> list[int]:
    """The K target tokens the metrics are computed over, for a prompt kind (§2.8)."""
    if prompt_kind in ("categorical", "magistral"):
        return verify_class_tokens_unique(tokenizer, leading_space=leading_space)
    return digit_token_ids(tokenizer)


def choose_leading_space(tokenizer, model=None, rendered: RenderedPrompt | None = None) -> bool:
    """Determine empirically which class-initial variant the model emits (§13 #3).

    Without a model to consult, prefer the space-prefixed variant (the class
    name follows ``**Confidence**:``); with a model, run one forward pass and
    check which variant contains the argmax next token.
    """
    if model is None or rendered is None:
        return True
    logits = final_logits(model, tokenizer, [rendered])[0]
    argmax = int(logits.argmax().item())
    for leading_space in (True, False):
        if argmax in set(class_token_ids(tokenizer, leading_space=leading_space)):
            return leading_space
    warnings.warn(
        "argmax next token is not a class-initial token; falling back to the "
        "space-prefixed variant (§2.2 sanity check should filter this trial)"
    )
    return True


# --------------------------------------------------------------------------- #
# Forward passes
# --------------------------------------------------------------------------- #


def pad_batch(rendered: list[RenderedPrompt], pad_id: int, device) -> tuple:
    """Right-pad a batch of rendered prompts (§15.3 — batch across trials).

    Right padding keeps every real token at its own index, so the per-trial
    positions found by :mod:`vconf.positions` stay valid.
    """
    lengths = [r.n_tokens for r in rendered]
    max_len = max(lengths)
    input_ids = torch.full((len(rendered), max_len), pad_id, dtype=torch.long)
    attention_mask = torch.zeros((len(rendered), max_len), dtype=torch.long)
    for i, r in enumerate(rendered):
        input_ids[i, : r.n_tokens] = torch.tensor(r.input_ids, dtype=torch.long)
        attention_mask[i, : r.n_tokens] = 1
    return input_ids.to(device), attention_mask.to(device), lengths


@torch.no_grad()
def final_logits(model, tokenizer, rendered: list[RenderedPrompt]) -> torch.Tensor:
    """Next-token logits at each prompt's final position — one forward pass (§2.2)."""
    device = next(model.parameters()).device
    input_ids, attention_mask, lengths = pad_batch(rendered, tokenizer.pad_token_id, device)
    out = model(input_ids=input_ids, attention_mask=attention_mask)
    idx = torch.tensor([n - 1 for n in lengths], device=device)
    return out.logits[torch.arange(len(rendered), device=device), idx, :].float()


@torch.no_grad()
def generate(model, tokenizer, rendered: list[RenderedPrompt], max_new_tokens: int) -> list[str]:
    """Greedy generation (temperature 0, §2.2) returning only the new text."""
    device = next(model.parameters()).device
    tokenizer.padding_side = "left"
    texts = [r.text for r in rendered]
    enc = tokenizer(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(device)
    out = model.generate(
        **enc,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        pad_token_id=tokenizer.pad_token_id,
    )
    tokenizer.padding_side = "right"
    new_tokens = out[:, enc["input_ids"].shape[1]:]
    return tokenizer.batch_decode(new_tokens, skip_special_tokens=True)


@torch.no_grad()
def greedy_next_token_ids(model, tokenizer, rendered: list[RenderedPrompt]) -> list[int]:
    """The first token ``generate`` actually emits, one prompt at a time (no padding)."""
    device = next(model.parameters()).device
    out = []
    for r in rendered:
        input_ids = torch.tensor([r.input_ids], device=device)
        generated = model.generate(
            input_ids=input_ids,
            attention_mask=torch.ones_like(input_ids),
            max_new_tokens=1,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
            repetition_penalty=1.0,
            pad_token_id=tokenizer.pad_token_id,
        )
        out.append(int(generated[0, input_ids.shape[1]]))
    return out


def sanity_check_forward_vs_generate(
    loaded: LoadedModel, rendered: list[RenderedPrompt], target_ids: list[int]
) -> dict:
    """§2.2 mandatory check, on a held-out sample.

    (a) the forward-pass argmax next token matches what ``generate`` produces and
    (b) that token is one of the valid class-initial tokens.  Trials failing
    either check must be filtered out of the analyses.
    """
    logits = final_logits(loaded.model, loaded.tokenizer, rendered)
    argmax = logits.argmax(dim=-1).tolist()
    generated = greedy_next_token_ids(loaded.model, loaded.tokenizer, rendered)
    matches = [g == a for g, a in zip(generated, argmax)]
    valid = [a in set(target_ids) for a in argmax]
    return {
        "n": len(rendered),
        "forward_matches_generate": sum(matches) / max(1, len(matches)),
        "argmax_is_valid_class": sum(valid) / max(1, len(valid)),
        "valid_mask": valid,
        "match_mask": matches,
    }
