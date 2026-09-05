"""Experiment 9 — Generalization suite (§12).

Four axes, each a re-run of Experiments 1–4 (and, where noted, 6) with one
component substituted: the numeric prompt, Qwen 2.5 7B, other datasets, and a
reasoning model with a chain-of-thought trace.  The invariant to check in every
case is that PANL plays a specific, causally sufficient role distinct from
PANL+1, with temporal precedence over CC.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch

from . import prompts as P
from .config import RunConfig, preset
from .data import QuestionItem
from .models import LoadedModel, render_prompt
from .pipeline import Trial, answer_token_span
from .positions import RenderedPrompt, trace_positions

#: §12.5 — the claim the suite evaluates.
GENERALIZATION_CLAIM = (
    "PANL plays a specific, causally sufficient role in verbal confidence "
    "generation, distinct from the immediately adjacent control position "
    "(PANL+1), with temporal precedence over CC wherever layer-wise analyses "
    "are performed."
)


@dataclass
class Axis:
    """One generalization axis and the expectations the manual states for it."""

    key: str
    description: str
    preset_name: str
    expected: dict


AXES: dict[str, Axis] = {
    "numeric": Axis(
        key="numeric",
        description="Axis 1 — numeric (0–100) confidence prompt, Gemma 3 27B, TriviaQA (§12.1)",
        preset_name="gemma-numeric",
        expected={
            "ece": 0.16, "auroc": 0.73, "baseline_confidence": 0.54,
            "steering_peaks": {"PANL": 25, "PANL+1": 31, "CC": 31},
            "patching_peaks": {"PANL": 25, "PANL+1": 0, "CC": 40},
            "noising_peaks": {"PANL": 26, "PANL+1": 26, "CC": 61},
            "swap_peaks": {"PANL": 26, "PANL+1": 31, "CC": 61},
            "steering_delta_confidence": {"PANL_high": 20, "PANL_low": -7,
                                          "CC_high": 37, "CC_low": -7},
            "steering_n": 124,
        },
    ),
    "qwen": Axis(
        key="qwen",
        description="Axis 2 — Qwen 2.5 7B Instruct, categorical prompt, TriviaQA (§12.2)",
        preset_name="qwen-categorical",
        expected={
            "ece": 0.06, "auroc": 0.65, "baseline_confidence": 0.56,
            "steering_peaks": {"PANL": 15, "PANL+1": 1, "CC": 22},
            "patching_peaks": {"PANL": 15, "PANL+1": 27, "CC": 27},
            "noising_peaks": {"PANL": 11, "PANL+1": 6, "CC": 21},
            "swap_peaks": {"PANL": 15, "PANL+1": 15, "CC": 27},
            "trial_counts": {"steering": 150, "patching": 200, "noising": 300, "swap": 200},
        },
    ),
    "bigmath": Axis(
        key="bigmath",
        description="Axis 3 — Big-Math, Gemma 3 27B, categorical prompt (§12.3)",
        preset_name="gemma-bigmath",
        expected={"accuracy": 0.402, "swap": "both directions visible"},
    ),
    "mmlu": Axis(
        key="mmlu",
        description="Axis 3 — MMLU, Gemma 3 27B, categorical prompt (§12.3)",
        preset_name="gemma-mmlu",
        expected={"accuracy": 0.768, "swap": "asymmetric, L->H dominant"},
    ),
    "magistral": Axis(
        key="magistral",
        description="Axis 4 — Magistral Small 2506 (24B, 40 layers), TriviaQA (§12.4)",
        preset_name="magistral",
        expected={
            "n_after_filtering": 4998,
            "almost_certain_share": 0.92,
            "patching": "substantial recovery at PANL; none at PANL+1",
            "noising": "no effect at PANL beyond control (dissociation); CC disrupts",
            "swap": "directional shifts at PANL, L->H dominant; none at PANL+1",
            "decoding": "PANL decodable; CC later; rising across the trace",
        },
    ),
}


def axis_config(axis_key: str) -> RunConfig:
    """The :class:`RunConfig` for one axis."""
    return preset(AXES[axis_key].preset_name)


# --------------------------------------------------------------------------- #
# Axis 4 — Magistral (§12.4)
# --------------------------------------------------------------------------- #


@torch.no_grad()
def run_magistral_phase0(
    loaded: LoadedModel,
    items: list[QuestionItem],
    cfg: RunConfig | None = None,
    max_new_tokens: int | None = None,
    batch_size: int | None = None,
    progress=None,
) -> list[Trial]:
    """Phase 1 of §12.4: chain-of-thought answer generation (§2.5.4).

    Records the full reasoning trace (on ``Trial.trace``) and the extracted final
    answer, so the Phase-2 prompt can present the whole response block back.
    """
    from .config import MAX_NEW_TOKENS_MAGISTRAL

    cfg = cfg or loaded.config
    batch_size = batch_size or cfg.batch_size
    max_new_tokens = max_new_tokens or MAX_NEW_TOKENS_MAGISTRAL
    tokenizer = loaded.tokenizer
    trials: list[Trial] = []
    batches = range(0, len(items), batch_size)
    iterator = progress(batches) if progress else batches
    for start in iterator:
        chunk = items[start: start + batch_size]
        rendered = [
            render_prompt(tokenizer, P.build_magistral_cot_prompt(item.question), cfg.use_chat_template)
            for item in chunk
        ]
        tokenizer.padding_side = "left"
        enc = tokenizer(
            [r.text for r in rendered], return_tensors="pt", padding=True, add_special_tokens=False
        ).to(loaded.device)
        out = loaded.model.generate(
            **enc, max_new_tokens=max_new_tokens, do_sample=False, temperature=None,
            top_p=None, top_k=None, repetition_penalty=1.0, return_dict_in_generate=True,
            output_scores=True, pad_token_id=tokenizer.pad_token_id,
        )
        tokenizer.padding_side = "right"
        generated = out.sequences[:, enc["input_ids"].shape[1]:]
        step_logprobs = torch.stack(
            [torch.log_softmax(score.float(), dim=-1) for score in out.scores]
        )
        chosen = torch.gather(
            step_logprobs.permute(1, 0, 2), 2, generated.unsqueeze(-1)
        ).squeeze(-1)
        for i, item in enumerate(chunk):
            ids, logprobs = [], []
            for j, token_id in enumerate(generated[i].tolist()):
                if token_id in (tokenizer.eos_token_id, tokenizer.pad_token_id):
                    break
                ids.append(token_id)
                logprobs.append(float(chosen[i, j]))
            text = tokenizer.decode(ids, skip_special_tokens=True)
            trace, answer = P.parse_magistral_answer(text)
            span = answer_token_span(tokenizer, ids, answer) if answer else None
            trials.append(
                Trial(
                    qid=item.qid,
                    question=item.question,
                    gold_answers=tuple(item.answers),
                    answer=answer,
                    answer_token_span=span,
                    answer_logprobs=logprobs[span[0]: span[1] + 1] if span else [],
                    trace=trace,
                    valid=bool(answer),
                )
            )
    return trials


def render_magistral_phase1(loaded: LoadedModel, trial: Trial, cfg: RunConfig | None = None) -> RenderedPrompt:
    """Phase 2 prompt: the trace plus the extracted answer, then the classes (§2.5.5)."""
    cfg = cfg or loaded.config
    built = P.build_magistral_confidence_prompt(trial.question, trial.trace, trial.answer)
    return render_prompt(loaded.tokenizer, built, cfg.use_chat_template)


def stratified_activation_set(
    trials: list[Trial], n: int = 3000, threshold: float = 0.7, seed: int = 0
) -> np.ndarray:
    """Retain all trials with confidence ≤ 0.7, fill the rest at random (§12.4)."""
    rng = np.random.default_rng(seed)
    low = [i for i, t in enumerate(trials) if (t.confidence or 0.0) <= threshold]
    high = [i for i, t in enumerate(trials) if (t.confidence or 0.0) > threshold]
    remaining = max(0, n - len(low))
    fill = rng.choice(high, size=min(remaining, len(high)), replace=False) if high else []
    return np.sort(np.array(list(low[:n]) + list(fill), dtype=int))


def extreme_trials(trials: list[Trial], n: int, high: bool, seed: int = 0) -> np.ndarray:
    """Draw from the extremes of the confidence distribution sorted by midpoint (§12.4)."""
    order = sorted(
        range(len(trials)), key=lambda i: (trials[i].confidence if trials[i].confidence is not None else 0.0)
    )
    picked = order[-n:] if high else order[:n]
    return np.sort(np.array(picked, dtype=int))


def magistral_corruption_spans(rendered: list[RenderedPrompt]) -> list[tuple[int, int]]:
    """Corruption scope for §12.4 patching.

    Under CoT the confidence-relevant content is distributed across the trace,
    so corruption spans the question and the entire response block (reasoning
    trace plus final answer), **excluding** the PANL newline itself and every
    downstream classification token.
    """
    from .positions import span_to_tokens

    spans = []
    for r in rendered:
        q_first, _ = span_to_tokens(r.offsets, r.spans["question"])
        spans.append((q_first, r.positions["PANL"] - 1))
    return spans


def magistral_trace_positions(rendered: RenderedPrompt, n_points: int = 10) -> dict[str, int]:
    """The ten ``Trace k%`` probing positions of §12.4."""
    return trace_positions(rendered.offsets, rendered.spans["trace"], n_points=n_points)


def magistral_probe_positions(rendered: RenderedPrompt) -> dict[str, int]:
    """Trace positions plus the five standard positions probed in §12.4."""
    out = dict(magistral_trace_positions(rendered))
    for name in ("PANL", "PANL+1", "CC", "last A", "QTT"):
        if name in rendered.positions:
            out["ALT" if name == "last A" else name] = rendered.positions[name]
    return out


def magistral_donor_lengths(rendered: list[RenderedPrompt]) -> tuple[np.ndarray, np.ndarray]:
    """Question length and *reasoning-trace* length, the two matching axes of §12.4."""
    from .positions import span_to_tokens

    q_len, trace_len = [], []
    for r in rendered:
        q_first, q_last = span_to_tokens(r.offsets, r.spans["question"])
        t_first, t_last = span_to_tokens(r.offsets, r.spans["trace"])
        q_len.append(q_last - q_first + 1)
        trace_len.append(t_last - t_first + 1)
    return np.array(q_len), np.array(trace_len)


# --------------------------------------------------------------------------- #
# The invariant
# --------------------------------------------------------------------------- #


def check_invariant(
    summary: pd.DataFrame,
    metric: str = "confidence_change_mean",
    control: str = "PANL+1",
) -> dict:
    """Does PANL separate from its control, and does it peak earlier than CC? (§12.5)"""
    out: dict = {}
    for position in ("PANL", control, "CC"):
        rows = summary[summary["position"] == position]
        if rows.empty:
            out[position] = None
            continue
        values = rows[metric].abs()
        out[position] = {
            "peak_layer": int(rows.loc[values.idxmax(), "layer"]),
            "peak_value": float(rows.loc[values.idxmax(), metric]),
        }
    panl, ctrl, cc = out.get("PANL"), out.get(control), out.get("CC")
    out["panl_exceeds_control"] = bool(
        panl and ctrl and abs(panl["peak_value"]) > abs(ctrl["peak_value"])
    )
    out["panl_precedes_cc"] = bool(panl and cc and panl["peak_layer"] < cc["peak_layer"])
    return out
