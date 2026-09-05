"""The two-phase protocol (§2.4) — the backbone every experiment consumes.

Phase 0 generates the model's *own* answer (recording per-token log-probabilities
and the answer token span); Phase 1 re-presents the question with that answer
inserted and reads the confidence from a **single forward pass** at the final
prompt position (§2.2).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch

from . import prompts as P
from .config import RunConfig
from .data import QuestionItem
from .models import (
    LoadedModel,
    final_logits,
    render_prompt,
    target_token_ids,
)
from .positions import RenderedPrompt


@dataclass
class Trial:
    """One question carried through both phases (§2.4)."""

    qid: str
    question: str
    gold_answers: tuple[str, ...] = ()
    answer: str = ""
    answer_logprobs: list[float] = field(default_factory=list)
    answer_token_span: tuple[int, int] | None = None
    phase0_class: str | None = None
    phase0_confidence: float | None = None
    phase0_numeric: int | None = None
    correct: bool | None = None
    class_logits: list[float] | None = None
    class_index: int | None = None
    confidence: float | None = None
    numeric_confidence: int | None = None
    #: Magistral only: the model's full chain-of-thought trace (§2.5.5).
    trace: str = ""
    valid: bool = True
    note: str = ""

    def to_json(self) -> dict:
        out = asdict(self)
        out["gold_answers"] = list(self.gold_answers)
        return out

    @classmethod
    def from_json(cls, blob: dict) -> "Trial":
        blob = dict(blob)
        blob["gold_answers"] = tuple(blob.get("gold_answers", ()))
        span = blob.get("answer_token_span")
        blob["answer_token_span"] = tuple(span) if span else None
        return cls(**blob)


def save_trials(trials: list[Trial], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([t.to_json() for t in trials]))
    return path


def load_trials(path: Path) -> list[Trial]:
    return [Trial.from_json(blob) for blob in json.loads(Path(path).read_text())]


# --------------------------------------------------------------------------- #
# Token bookkeeping
# --------------------------------------------------------------------------- #


def token_char_offsets(tokenizer, token_ids: list[int]) -> list[tuple[int, int]]:
    """Character spans of each token within ``tokenizer.decode(token_ids)``.

    Computed by incremental decoding so it works for any tokenizer, including
    those whose ``decode`` is not a plain concatenation of per-token strings.
    """
    offsets: list[tuple[int, int]] = []
    previous = 0
    for i in range(len(token_ids)):
        length = len(tokenizer.decode(token_ids[: i + 1]))
        offsets.append((previous, length))
        previous = length
    return offsets


def answer_token_span(
    tokenizer, token_ids: list[int], answer: str
) -> tuple[int, int] | None:
    """Map the extracted answer string back onto the generated token sequence (§2.4)."""
    text = tokenizer.decode(token_ids)
    start = text.find(answer)
    if start == -1 or not answer:
        return None
    end = start + len(answer)
    offsets = token_char_offsets(tokenizer, token_ids)
    covering = [i for i, (a, b) in enumerate(offsets) if a < end and b > start]
    if not covering:
        return None
    return covering[0], covering[-1]


# --------------------------------------------------------------------------- #
# Phase 0 — answer generation
# --------------------------------------------------------------------------- #


@torch.no_grad()
def run_phase0(
    loaded: LoadedModel,
    items: list[QuestionItem],
    cfg: RunConfig | None = None,
    max_new_tokens: int | None = None,
    batch_size: int | None = None,
    progress=None,
) -> list[Trial]:
    """Generate the model's own answer for each question, greedily (§2.4 Phase 0).

    Records the answer string, the per-token log-probabilities of the generated
    sequence restricted to the answer span, the answer token span itself, and
    the Phase-0 verbal confidence report.
    """
    cfg = cfg or loaded.config
    tokenizer = loaded.tokenizer
    device = loaded.device
    batch_size = batch_size or cfg.batch_size
    kind = P.PHASE0_KIND[cfg.prompt_kind]
    max_new_tokens = max_new_tokens or cfg.max_new_tokens_phase0

    trials: list[Trial] = []
    batches = range(0, len(items), batch_size)
    iterator = progress(batches) if progress else batches
    for start in iterator:
        chunk = items[start: start + batch_size]
        rendered = [
            render_prompt(tokenizer, P.build_phase0_prompt(item.question, kind), cfg.use_chat_template)
            for item in chunk
        ]
        tokenizer.padding_side = "left"
        enc = tokenizer(
            [r.text for r in rendered], return_tensors="pt", padding=True, add_special_tokens=False
        ).to(device)
        out = loaded.model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
            repetition_penalty=1.0,
            return_dict_in_generate=True,
            output_scores=True,
            pad_token_id=tokenizer.pad_token_id,
        )
        tokenizer.padding_side = "right"
        prompt_len = enc["input_ids"].shape[1]
        generated = out.sequences[:, prompt_len:]
        # (steps, batch) log-probabilities of the tokens actually chosen
        step_logprobs = torch.stack(
            [torch.log_softmax(score.float(), dim=-1) for score in out.scores]
        )
        chosen = torch.gather(
            step_logprobs.permute(1, 0, 2), 2, generated.unsqueeze(-1)
        ).squeeze(-1)

        for i, item in enumerate(chunk):
            ids = generated[i].tolist()
            keep = []
            for j, token_id in enumerate(ids):
                if token_id in (tokenizer.eos_token_id, tokenizer.pad_token_id):
                    break
                keep.append(j)
            ids = [ids[j] for j in keep]
            logprobs = [float(chosen[i, j]) for j in keep]
            text = tokenizer.decode(ids, skip_special_tokens=True)
            answer = P.parse_answer(text)
            span = answer_token_span(tokenizer, ids, answer)
            trial = Trial(
                qid=item.qid,
                question=item.question,
                gold_answers=tuple(item.answers),
                answer=answer,
                answer_token_span=span,
                answer_logprobs=logprobs[span[0]: span[1] + 1] if span else [],
            )
            if kind == "categorical":
                cls = P.parse_class(text[len(answer):])
                trial.phase0_class = cls
                trial.phase0_confidence = P.CLASS_MIDPOINT[cls] if cls else None
            else:
                scale = 100 if kind == "numeric" else 9
                idx = text.find(P.CONFIDENCE_CUE)
                tail = text[idx + len(P.CONFIDENCE_CUE):] if idx != -1 else text[len(answer):]
                value = P.parse_numeric_confidence(tail, scale=scale)
                trial.phase0_numeric = value
                trial.phase0_confidence = value / scale if value is not None else None
            if not answer or span is None:
                trial.valid = False
                trial.note = "empty answer or unmappable answer span"
            trials.append(trial)
    return trials


# --------------------------------------------------------------------------- #
# Phase 1 — confidence elicitation
# --------------------------------------------------------------------------- #


def render_phase1(loaded: LoadedModel, trial: Trial, cfg: RunConfig | None = None) -> RenderedPrompt:
    """Build the Phase-1 prompt with the model's *own* answer inserted (§2.4)."""
    cfg = cfg or loaded.config
    built = P.build_confidence_prompt(trial.question, trial.answer, cfg.prompt_kind)
    return render_prompt(loaded.tokenizer, built, cfg.use_chat_template)


@torch.no_grad()
def run_phase1(
    loaded: LoadedModel,
    trials: list[Trial],
    cfg: RunConfig | None = None,
    batch_size: int | None = None,
    progress=None,
) -> list[RenderedPrompt]:
    """One forward pass per trial; fills in the clean class logits/index/confidence."""
    cfg = cfg or loaded.config
    batch_size = batch_size or cfg.batch_size
    ids = target_token_ids(loaded.tokenizer, cfg.prompt_kind)
    scale = 100 if cfg.prompt_kind == "numeric" else (9 if cfg.prompt_kind == "minimal_numeric" else None)
    rendered_all: list[RenderedPrompt] = []
    batches = range(0, len(trials), batch_size)
    iterator = progress(batches) if progress else batches
    for start in iterator:
        chunk = trials[start: start + batch_size]
        rendered = [render_phase1(loaded, trial, cfg) for trial in chunk]
        logits = final_logits(loaded.model, loaded.tokenizer, rendered)
        class_logits = logits[:, ids].cpu().numpy()
        for i, trial in enumerate(chunk):
            trial.class_logits = [float(v) for v in class_logits[i]]
            trial.class_index = int(class_logits[i].argmax())
            if scale is None:
                trial.confidence = P.CLASS_MIDPOINT[P.CLASSES[trial.class_index]]
            else:
                trial.numeric_confidence = trial.class_index
                trial.confidence = trial.class_index / 9.0 if scale == 9 else None
        rendered_all.extend(rendered)
    return rendered_all


@torch.no_grad()
def generate_numeric_confidence(
    loaded: LoadedModel, trials: list[Trial], cfg: RunConfig | None = None,
    batch_size: int | None = None,
) -> None:
    """Generate the full integer for the numeric prompt (``max_new_tokens=4``, §2.2)."""
    from .config import MAX_NEW_TOKENS_NUMERIC
    from .models import generate

    cfg = cfg or loaded.config
    batch_size = batch_size or cfg.batch_size
    scale = 100 if cfg.prompt_kind == "numeric" else 9
    for start in range(0, len(trials), batch_size):
        chunk = trials[start: start + batch_size]
        rendered = [render_phase1(loaded, trial, cfg) for trial in chunk]
        texts = generate(loaded.model, loaded.tokenizer, rendered, MAX_NEW_TOKENS_NUMERIC)
        for trial, text in zip(chunk, texts):
            value = P.parse_numeric_confidence(text, scale=scale)
            trial.numeric_confidence = value
            trial.confidence = value / scale if value is not None else None
            if value is None:
                trial.valid = False
                trial.note = "no parsable numeric confidence"


def filter_valid(trials: list[Trial], target_ids: list[int] | None = None) -> list[Trial]:
    """Drop trials without a valid answer or a valid confidence report (§2.2, §12.4)."""
    return [t for t in trials if t.valid and t.class_index is not None and t.answer]


def confidences(trials: list[Trial]) -> np.ndarray:
    return np.array([t.confidence if t.confidence is not None else np.nan for t in trials])


def class_indices(trials: list[Trial]) -> np.ndarray:
    return np.array([t.class_index for t in trials], dtype=int)


def clean_class_logits(trials: list[Trial]) -> np.ndarray:
    return np.array([t.class_logits for t in trials], dtype=float)


def correctness(trials: list[Trial]) -> np.ndarray:
    return np.array([bool(t.correct) for t in trials], dtype=int)


def filter_positions_isolable(
    loaded: LoadedModel, trials: list[Trial], cfg: RunConfig | None = None
) -> tuple[list[Trial], list[RenderedPrompt]]:
    """Keep only trials whose Phase-1 prompt isolates PANL as its own token (§2.6).

    Answers ending in punctuation can be merged with the following newline by
    BPE tokenizers; §14.3 lists exactly this as the cause of a PANL/PANL+1
    dissociation failure, so such trials are dropped rather than analysed.
    """
    from .models import panl_is_isolated

    cfg = cfg or loaded.config
    kept, rendered_kept = [], []
    for trial in trials:
        try:
            rendered = render_phase1(loaded, trial, cfg)
        except Exception:  # position could not be located at all
            trial.valid = False
            trial.note = "position location failed"
            continue
        if panl_is_isolated(rendered, loaded.tokenizer):
            kept.append(trial)
            rendered_kept.append(rendered)
        else:
            trial.valid = False
            trial.note = "PANL merged with the preceding token"
    return kept, rendered_kept


def collect_trials(
    loaded: LoadedModel,
    items: list[QuestionItem],
    cfg: RunConfig | None = None,
    target_n: int | None = None,
    chunk: int = 64,
    progress=None,
) -> tuple[list[Trial], list[RenderedPrompt]]:
    """Run both phases over ``items`` until ``target_n`` usable trials are collected.

    "Usable" means: a non-empty answer whose token span could be mapped, a PANL
    that is its own token (§2.6), and a valid confidence report (§2.2 — filter
    out any trial where the sanity check fails).  Because a trial can be lost at
    any of those steps, ``items`` should be larger than ``target_n``.
    """
    cfg = cfg or loaded.config
    target_n = target_n or len(items)
    trials: list[Trial] = []
    rendered: list[RenderedPrompt] = []
    for start in range(0, len(items), chunk):
        batch_items = items[start: start + chunk]
        raw = run_phase0(loaded, batch_items, cfg, progress=progress)
        kept, _ = filter_positions_isolable(loaded, raw, cfg)
        kept = [t for t in kept if t.valid]
        rendered_batch = run_phase1(loaded, kept, cfg, progress=progress)
        for trial, rend in zip(kept, rendered_batch):
            if trial.class_index is None:
                continue
            trials.append(trial)
            rendered.append(rend)
        if len(trials) >= target_n:
            break
    return trials[:target_n], rendered[:target_n]
