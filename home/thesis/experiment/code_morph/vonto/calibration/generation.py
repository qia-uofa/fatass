"""Generation — the paper's Phase 0: the confidence-instruction block moved to
the *start*, the prompt forced to end at ``**Answer**:`` (the answer-colon
position, reproduction guidebook §2.4), and the model's own completion from
there greedy-decoded as its answer — recording per-answer-token log-
probability and full-distribution entropy along the way, so
`ground_truth.ProbabilityGT`/`EntropyGT` need no extra forward pass later to
grade it.

Phase 0 is otherwise construct-agnostic (06-generalized-method.tex: "the
model produces an answer from the inquiry") — front-loading a sentiment's own
instruction block is opt-in via ``sentiment_om``, off by default. The paper's
own Phase 0 specifically front-loaded `ConfidenceOM`'s instructions
unconditionally (`archive/vconf/prompts.py:build_phase0_prompt`'s ``sentiment``
parameter defaulted to confidence), but that was never re-examined when vonto
generalized Phase 0 to constructs the paper never covers at all (list variety,
20-questions impurity) — there, priming the model to rate its own correctness
before asking it to generate a list or propose a strategic question is an
undisclosed confound, not a documented part of the generalized method. Pass
``sentiment_om=ConfidenceOM()`` explicitly at the one call site that's
actually replicating the paper's own confidence experiment; leave it unset
everywhere else.
"""

from __future__ import annotations

from ..dataset import Inquiry, Trial
from ..observation_method.likert_om import HEADER, LikertOM

ANSWER_CUE = "**Answer**:"


def _phase0_prompt(question: str, sentiment_om: LikertOM | None = None) -> str:
    if sentiment_om is None:
        return f"{HEADER}Question: {question}\n"
    return f"{sentiment_om.instructions}\n\n{HEADER}Question: {question}\n"


def generate_trial(
    loaded, seed: object, inquiry: Inquiry, max_new_tokens: int = 200, sentiment_om: LikertOM | None = None,
) -> Trial:
    """Decode ``inquiry.question`` against ``loaded`` under the Phase-0
    prompt, returning the resulting `Trial`. ``inquiry.temperature`` actually
    drives generation now: ``0`` (or falsy) means greedy, matching the
    paper's own "greedy decoding, temperature = 0" requirement (§2.1, §2.2)
    for the calibration datasets that must stay reproducible that way;
    anything greater than ``0`` means real sampling at that temperature, seeded
    by ``inquiry.generation_seed`` when given. This transformers version's
    ``generate()`` has no ``generator=`` parameter to scope a seed to just
    this call (checked directly: it's rejected as an unrecognized kwarg), so
    reproducibility here means seeding the *global* torch RNG
    (``torch.manual_seed``) immediately before the call — a real, if narrow,
    side effect: it perturbs whatever the global RNG state would otherwise
    have been for anything running after this call, the same caveat any
    ``torch.manual_seed`` call anywhere carries.

    A subtlety this handles rather than ignores: when sampling,
    ``output_scores`` returns the *temperature-scaled* logits
    (``raw_logits / temperature`` — verified directly against a plain forward
    pass, not assumed), not the model's own raw distribution. Left as-is,
    ``answer_logprobs``/``answer_entropies`` would become artifacts of
    whatever temperature this particular inquiry happened to use rather than
    a genuine property of the model's own confidence — so the scaling is
    undone (``raw_logits * temperature``) before computing them, keeping both
    quantities comparable across trials regardless of sampling temperature.
    ``top_p=1.0``/``top_k=0`` (no truncation) when sampling is what makes this
    exact rather than approximate: temperature is the *only* transform
    applied to the scores, so it's exactly invertible.

    ``sentiment_om``, when given, front-loads that observation method's own
    instruction block ahead of the question (the paper's own confidence-
    specific Phase 0 design) — leave unset for a construct-agnostic Phase 0
    that just asks the question, no self-rating framing attached.

    If ``seed`` carries a ``precomputed_response`` (duck-typed —
    `vonto.dataset.twenty_questions_dataset.Game` is the only current
    example), no generation happens at all: the `Trial` is built directly
    from that already-real value rather than resynthesizing one under a
    differently-framed prompt. This is for seeds whose "answer" was already
    produced by a genuine, dataset-specific generation earlier (e.g. a
    20-Questions game's own last real question) — going through Phase 0
    again here would score a *different*, freshly-generated response instead
    of the one that actually happened.
    """
    precomputed = getattr(seed, "precomputed_response", None)
    if precomputed is not None:
        return Trial(seed=seed, inquiry=inquiry, response=precomputed, answer_logprobs=[], answer_entropies=[])

    import torch

    do_sample = bool(inquiry.temperature and inquiry.temperature > 0)
    if do_sample and inquiry.generation_seed is not None:
        torch.manual_seed(inquiry.generation_seed)

    body = _phase0_prompt(inquiry.question, sentiment_om)
    text = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": body}], tokenize=False, add_generation_prompt=True
    )
    text += ANSWER_CUE
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    with torch.no_grad():
        out = loaded.model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=inquiry.temperature if do_sample else None,
            top_p=1.0 if do_sample else None,
            top_k=0 if do_sample else None,
            pad_token_id=loaded.tokenizer.pad_token_id,
            return_dict_in_generate=True,
            output_scores=True,
            # Without a stop, the model happily keeps going past the answer and
            # straight into its own confidence report (it can see those very
            # instructions in the Phase-0 prompt) -- a blank line is the natural
            # boundary of a short factual answer, and stopping there keeps
            # `response`/`answer_logprobs`/`answer_entropies` scoped to just the
            # answer, matching the paper's own answer-token-span framing (§2.4)
            # without needing full answer-string extraction. Per-`Inquiry`
            # (`inquiry.stop_strings`), not hardcoded here: a naturally
            # long/multi-line answer (e.g. a 20-item list) needs `None`, or
            # generation stops at the first blank line the model writes --
            # typically the transition *into* the actual content.
            stop_strings=list(inquiry.stop_strings) if inquiry.stop_strings else None,
            tokenizer=loaded.tokenizer,
        )
    new_tokens = out.sequences[0, enc["input_ids"].shape[1] :]
    response = loaded.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    answer_logprobs: list[float] = []
    answer_entropies: list[float] = []
    for step_logits, token_id in zip(out.scores, new_tokens):
        raw_logits = step_logits[0].float()
        if do_sample:
            raw_logits = raw_logits * inquiry.temperature  # undo the scaling output_scores applied
        log_probs = torch.log_softmax(raw_logits, dim=-1)
        answer_logprobs.append(float(log_probs[token_id]))
        probs = log_probs.exp()
        answer_entropies.append(float(-(probs * log_probs).sum()))

    return Trial(
        seed=seed,
        inquiry=inquiry,
        response=response,
        answer_logprobs=answer_logprobs,
        answer_entropies=answer_entropies,
    )
