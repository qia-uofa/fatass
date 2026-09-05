"""Activation steering (reproduction guidebook §4): extract a steering
vector from the difference between high- and low-*self-reported* trials'
own residual-stream activations at one (layer, position), inject it back in
at observation time, and measure the shift it causes in the same self-report.

Scoped down from the paper's full grid (4 positions × 2 directions × 2
scales × 22 layers × 200 trials, aimed at Gemma 3 27B's 3,000-trial
activation-collection set) -- still a handful of layers by default, not a
dense per-layer sweep, unless the caller passes a full ``range(n_layers)``.
Several things an earlier version of this module got wrong or skipped
entirely are now handled, because a null result is uninterpretable without
them:

1. **Control positions, not just PANL.** `POSITIONS` is `("PANL", "PANL+1",
   "FCC", "CC")` -- PANL is the paper's key, falsifying position (§4.1);
   PANL+1 is its mandatory control, one token away, that must show nothing;
   FCC is the secondary control inside the instructions block's own
   format-example sentence; CC is the paper's other key position
   (verbalization site, later layers). Without ever measuring a control, a
   flat result at PANL alone can't be told apart from "no representation
   here" vs. "this whole intervention mechanism does nothing."
2. **Both directions.** `steering_effect` always tests `+alpha*v` (steer
   toward the high pole) and `-alpha*v` (steer toward the low pole) on the
   same test trials -- never just one. "Strong, bidirectional, graded"
   (§4.6) is part of the actual claim, not an optional extra.
3. **Disjoint extraction/test pools.** The vector is built from
   `extraction_trials`; its effect is measured on a *different* list,
   `test_trials` (see `calibration.generate_disjoint_pools`) -- matching
   §2.3.4's explicit disjointness requirement. Passing the same list for
   both (an earlier version of this module did) lets a trial's own
   activation partly build the very vector that then steers it.
4. **AC, via a genuinely different mechanism.** AC lives in the Phase-0
   prompt, a separate forward pass from the one every other position reads
   from -- `residual_at_ac`/`build_ac_steering_vector`/`ac_steering_effect`
   are kept as their own, parallel set of functions (not folded into
   `POSITIONS`) because testing AC means *regenerating* the answer under
   intervention, not a single forward pass; see the "AC" section below for
   the full reasoning.

Also fixed: **extraction ranks by the observation method's own self-report**
(§4.2: "the 25 highest-ranked trials by confidence, i.e. class 'Almost
certain'"), not by a paired ground truth's value -- a ground truth plays no
role in the paper's steering experiment at all; that axis belongs to
Experiment 0/`calibration.py`'s own cross-product sweep, not this one. An
optional `correctness` ground truth restricts the extraction pool to its own
top (better) half (`_filter_by_gt` -- a *relative* rank split, not a fixed
threshold: `CorrectnessGT`'s values are exactly 0.0/1.0, but `EntropyGT` is
unbounded raw nats and `ImpurityGT` tops out at 0.5, so a fixed `>= 0.5`
threshold would silently keep almost everything or almost nothing for those)
for constructs where restricting to some real correlate of correctness is
meaningful; pass `None` to skip filtering entirely.

Still not implemented: class-balanced *extraction* pools drawn from a real
3,000-trial activation set (there's no such large pool available here -- the
extraction pool here doubles as its own small, unbalanced sample); a
class-balanced *test* set is handled separately, see
`select_balanced_test_trials` (§2.7: the model favors high-confidence-style
classes on every Likert scale here, so an unbalanced test set under-samples
the low pole and can't test bidirectional steering meaningfully).
"""

from __future__ import annotations

import dataclasses
from statistics import mean

import torch
from scipy.stats import sem as _sem
from tqdm.auto import tqdm

from ..ground_truth import GroundTruth
from ..observation_method import LikertOM
from .generation import ANSWER_CUE, _phase0_prompt
from .observation import compose_self_report_inquiry


def _filter_by_gt(pool: list, gt: GroundTruth) -> list:
    """The top (better) half of ``pool`` by ``gt``'s own value — a *relative*
    rank split, not an absolute threshold. §4.2 only ever needs this for
    ``CorrectnessGT`` ("restricted to trials the model answered correctly"),
    where every value is exactly 0.0 or 1.0 and a fixed 0.5 threshold happens
    to reduce to "keep the 1.0s" — but nothing else here is bounded that way:
    `ImpurityGT` tops out at 0.5 (Gini impurity of a two-way split can never
    exceed that), and `EntropyGT` is raw summed nats, unbounded above. A
    fixed ``>= 0.5`` threshold against either would silently keep almost
    nothing (`ImpurityGT`) or almost everything (`EntropyGT`), not a
    meaningful "good half." A relative split works the same way regardless
    of the GT's own range or whether higher is "better" in some absolute
    sense — it just keeps the pool's own better-half trials by that GT.
    """
    values = gt.values(pool)
    order = sorted(range(len(pool)), key=lambda i: values[i], reverse=True)
    keep = order[: max(1, -(-len(pool) // 2))]  # ceil(len(pool) / 2)
    return [pool[i] for i in sorted(keep)]

#: PANL (key, falsifying position, §4.1), PANL+1 (mandatory control), FCC
#: (secondary control, inside the instructions block), CC (key,
#: verbalization site, later layers). AC is deliberately not in this tuple —
#: it lives in the Phase-0 (answer-generation) prompt, a different forward
#: pass entirely from the one every position here reads from, and needs a
#: fundamentally different (regeneration-based) intervention mechanism; see
#: `residual_at_ac`/`ac_steering_effect` below and the module docstring.
POSITIONS: tuple[str, ...] = ("PANL", "PANL+1", "FCC", "CC")


def _rendered_prompt_and_positions(loaded, om: LikertOM, trial) -> tuple[str, dict[str, int]]:
    """The forced-completion-cue self-report text for ``trial`` under ``om``
    (chat-templated body + appended ``"**Name**:"`` cue — `LikertOM.observe`'s
    own shape), plus every position in `POSITIONS`' token index within it.

    CC is always the text's own last token — the cue is appended with
    nothing after it, exactly where `LikertOM.observe` reads logits from, so
    no separate offset-tracking is needed for it. PANL is located the same
    structural way `LikertOM.build_prompt_with_positions` already does for
    `calibration.observation.verify_positions`; PANL+1 is simply the next
    token in the same tokenization. FCC (§2.6: "the colon preceding $CLASS
    in the instruction block") is a *different*, earlier occurrence of a
    similar-looking cue than CC — it's the colon inside `om.instructions`'
    own format-example sentence (``"**Name**: $CLASS"``, see
    `LikertOM.instructions`), located the same structural way as PANL:
    string search within ``om.instructions`` for its own known literal
    text, not a hardcoded offset. Reusing PANL's and FCC's indices (computed
    by tokenizing the templated text *without* the cue) for the version
    *with* the cue appended is safe: BPE tokenizers are prefix-stable well
    away from an edit site, and both sit far from the text's own end.
    """
    prompt, offsets = om.build_prompt_with_positions(compose_self_report_inquiry(trial))
    templated = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
    )
    shift = templated.find(prompt)
    if shift < 0:
        raise ValueError("chat template altered the prompt body -- cannot map PANL onto it")
    panl_char_index = offsets["PANL"] + shift

    fcc_marker = f"**{om.name.capitalize()}**: $CLASS"
    marker_offset = om.instructions.index(fcc_marker)
    # `build_prompt_with_positions` places `self.instructions` right after
    # PANL's own newline character: `f"{HEADER}{question}\n{instructions}"`.
    instructions_start = offsets["PANL"] + 1
    fcc_char_index = instructions_start + marker_offset + fcc_marker.index(":") + shift

    enc = loaded.tokenizer(templated, add_special_tokens=False, return_offsets_mapping=True)

    def _token_at(char_index: int, label: str) -> int:
        for i, (start, end) in enumerate(enc["offset_mapping"]):
            if start <= char_index < end:
                return i
        raise ValueError(f"no token covers {label}'s character offset")

    panl_index = _token_at(panl_char_index, "PANL")
    fcc_index = _token_at(fcc_char_index, "FCC")

    cue = f"**{om.name.capitalize()}**:"
    text = templated + cue
    full_ids = loaded.tokenizer(text, add_special_tokens=False)["input_ids"]
    cc_index = len(full_ids) - 1

    return text, {"PANL": panl_index, "PANL+1": panl_index + 1, "FCC": fcc_index, "CC": cc_index}


def residual_at_position(loaded, om: LikertOM, trial, layer: int, position: str) -> torch.Tensor:
    """The residual-stream activation at ``position`` (one of `POSITIONS`),
    output of decoder layer ``layer``, for one trial's own self-report
    prompt — a single forward pass with a hook, no generation."""
    text, positions = _rendered_prompt_and_positions(loaded, om, trial)
    index = positions[position]
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)

    captured: dict[str, torch.Tensor] = {}

    def hook(module, inputs, output):
        captured["activation"] = output[0, index].detach().clone()

    handle = loaded.model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.no_grad():
            loaded.model(**enc)
    finally:
        handle.remove()
    return captured["activation"]


def build_steering_vector(
    loaded, om: LikertOM, extraction_trials: list, layer: int, position: str,
    top_n: int = 5, correctness: GroundTruth | None = None,
) -> torch.Tensor:
    """The paper's own construction (§4.2), generalized to any `LikertOM`:
    rank ``extraction_trials`` by ``om``'s *own* clean self-report midpoint
    (never a separate ground truth — see the module docstring), optionally
    first restricted to the top (better) half of the pool by ``correctness``
    (see `_filter_by_gt`; pass ``None`` to skip filtering entirely). ``H``/
    ``L`` = the top-/bottom-``top_n`` by that ranking; ``v = mean(H) -
    mean(L)``, scaled to 3% of the mean residual norm at (``layer``,
    ``position``) over the (possibly filtered) extraction pool. ``top_n``
    defaults far below the paper's own 25 — this pool has nowhere near a
    3,000-trial activation-collection set to draw from — and is clamped to
    at most half the (filtered) pool so ``H``/``L`` never overlap.

    ``extraction_trials`` should be disjoint from whatever trials the
    resulting vector is later tested on — see
    `calibration.generate_disjoint_pools` — this function itself has no way
    to enforce that; it only ever sees one pool.
    """
    pool = extraction_trials
    if correctness is not None:
        pool = _filter_by_gt(pool, correctness)
        if len(pool) < 2:
            raise ValueError(
                f"only {len(pool)}/{len(extraction_trials)} extraction trials kept after filtering "
                f"by {correctness.name} -- too few to build a steering vector"
            )

    midpoints = [
        om.observe(loaded, om.build_prompt(compose_self_report_inquiry(t)))[1]
        for t in tqdm(pool, desc=f"{om.name}: ranking extraction pool", leave=False)
    ]
    order = sorted(range(len(pool)), key=lambda i: midpoints[i])
    top_n = max(1, min(top_n, len(pool) // 2))
    low_idx, high_idx = order[:top_n], order[-top_n:]

    activations = [
        residual_at_position(loaded, om, t, layer, position)
        for t in tqdm(pool, desc=f"{om.name}: capturing {position} activations @ L{layer}", leave=False)
    ]
    mean_norm = torch.stack([a.norm() for a in activations]).mean()

    high = torch.stack([activations[i] for i in high_idx]).mean(dim=0)
    low = torch.stack([activations[i] for i in low_idx]).mean(dim=0)
    v = high - low
    return v / v.norm() * (0.03 * mean_norm)


def select_balanced_test_trials(loaded, om: LikertOM, candidate_trials: list, n_test: int) -> list:
    """``n_test`` trials from ``candidate_trials``, half the lowest-ranked
    and half the highest-ranked by ``om``'s own clean self-report midpoint —
    a *relative* split, not §2.7's literal "half from the top-3 classes,
    half from the bottom-3" fixed absolute thresholds. Checked directly
    against real trials: Qwen's `CommitmentOM` landed in the bottom three
    (of ten) classes on **0 of 30** real `SynonymsDataset` candidates — a
    fixed-threshold version of this function fails outright on that real
    distribution, every time. A relative split always produces a genuine
    low-vs-high contrast as long as the candidate pool has any spread at
    all, which is exactly the guidebook's own fallback for the same
    narrow-distribution problem (§2.7's Qwen-specific adjustment moves the
    H/L classes inward rather than assuming the paper's own top-3/bottom-3
    holds on every model).

    ``candidate_trials`` should be an oversampled pool (comfortably more
    than ``n_test``), since only the extremes are kept. Raises if there
    aren't enough candidates, or if the selected low/high halves land on the
    identical self-report value (no real contrast to steer between).
    """
    if len(candidate_trials) < n_test:
        raise ValueError(
            f"{om.name}: only {len(candidate_trials)} candidates, need >= {n_test} to select a "
            f"balanced test set"
        )
    midpoints = [
        om.observe(loaded, om.build_prompt(compose_self_report_inquiry(t)))[1]
        for t in tqdm(candidate_trials, desc=f"{om.name}: classifying candidates for balanced sampling", leave=False)
    ]
    order = sorted(range(len(candidate_trials)), key=lambda i: midpoints[i])
    half = n_test // 2
    low_idx, high_idx = order[:half], order[-(n_test - half):]
    if midpoints[low_idx[-1]] == midpoints[high_idx[0]]:
        raise ValueError(
            f"{om.name}: every one of {len(candidate_trials)} candidates landed on the same "
            f"self-report value ({midpoints[low_idx[-1]]:.2f}) -- no low/high contrast to build a "
            f"balanced test set from"
        )
    return [candidate_trials[i] for i in low_idx] + [candidate_trials[i] for i in high_idx]


def _class_logits(
    loaded, om: LikertOM, trial, layer: int, position: str, vector: torch.Tensor | None, alpha: float,
) -> torch.Tensor:
    """One forward pass's logits over ``om.classes``' own first tokens —
    clean when ``vector`` is ``None``, else with ``alpha * vector`` added to
    the residual stream at (``layer``, ``position``)."""
    text, positions = _rendered_prompt_and_positions(loaded, om, trial)
    index = positions[position]
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    class_ids = [loaded.tokenizer(" " + c, add_special_tokens=False)["input_ids"][0] for c in om.classes]

    handle = None
    if vector is not None:
        def hook(module, inputs, output):
            output[0, index] = output[0, index] + alpha * vector
            return output

        handle = loaded.model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.no_grad():
            logits = loaded.model(**enc).logits[0, -1]
    finally:
        if handle is not None:
            handle.remove()
    return logits[class_ids]


def _logit_diff(class_logits: torch.Tensor, y: int) -> float:
    """§2.8 (1): the logit of class ``y`` minus the mean logit of every
    other class."""
    others_mean = (class_logits.sum() - class_logits[y]) / (len(class_logits) - 1)
    return float(class_logits[y] - others_mean)


def _direction_summary(deltas: list[float], logit_diff_changes: list[float], changed: list[bool]) -> dict:
    """Shared by `steering_effect` and `ac_steering_effect` — one
    direction's (high or low) worth of per-trial results, reduced to the
    same summary shape both report."""
    return {
        "delta": deltas,
        "mean_delta": mean(deltas),
        "sem_delta": float(_sem(deltas)) if len(deltas) > 1 else float("nan"),
        "logit_diff_change": logit_diff_changes,
        "mean_logit_diff_change": mean(logit_diff_changes),
        "change_rate": sum(changed) / len(changed),
    }


def observe_with_steering(
    loaded, om: LikertOM, trial, layer: int, position: str, vector: torch.Tensor, alpha: float,
) -> tuple[str, float]:
    """Re-run ``om``'s own self-report elicitation about ``trial`` with
    ``alpha * vector`` added to the residual stream at ``position``, output
    of decoder layer ``layer`` (§4.3) — returns ``(winning_class,
    midpoint)``, the same shape as `LikertOM.observe`, under the steered
    forward pass instead of the clean one. A thin wrapper over
    `_class_logits`; `steering_effect` calls `_class_logits` directly since
    it also needs the raw logits for the logit-difference/change-rate
    metrics, not just the winning class.
    """
    class_logits = _class_logits(loaded, om, trial, layer, position, vector, alpha)
    winner = om.classes[int(class_logits.argmax())]
    return winner, om.class_midpoints[winner]


def steering_effect(
    loaded, om: LikertOM, extraction_trials: list, test_trials: list, layer: int, position: str,
    alpha: float, top_n: int = 5, correctness: GroundTruth | None = None,
) -> dict:
    """Build the steering vector from ``extraction_trials`` (§4.2, ranked by
    ``om``'s own self-report — see `build_steering_vector` — and disjoint
    from ``test_trials``, see `calibration.generate_disjoint_pools`), then
    for every trial in ``test_trials`` compare its clean class-logit read
    against both a high-direction (``+alpha*v``) and low-direction
    (``-alpha*v``) steered read at (``layer``, ``position``) — §4.4's
    "directions: high-confidence steering and low-confidence steering",
    never just one.

    Reports, per direction: the per-trial self-report-midpoint delta (mean +
    SEM across ``test_trials``), the logit-difference *change* (§2.8 (1) —
    the target class ``y`` is fixed at the clean prediction for both the
    clean and steered reads, per the guidebook: "Always report the change,
    keeping the target class y fixed at the clean prediction"), and the
    first-token change rate (§2.8 (3) — the fraction of trials whose steered
    argmax class differs from its clean one).
    """
    vector = build_steering_vector(
        loaded, om, extraction_trials, layer, position, top_n=top_n, correctness=correctness,
    )

    clean_midpoints, clean_logit_diffs, clean_winner_idx = [], [], []
    high_midpoints, high_logit_diff_changes, high_changed = [], [], []
    low_midpoints, low_logit_diff_changes, low_changed = [], [], []

    for trial in tqdm(test_trials, desc=f"{om.name}: {position} steering @ L{layer}", leave=False):
        clean_logits = _class_logits(loaded, om, trial, layer, position, None, 0.0)
        y = int(clean_logits.argmax())
        clean_winner_idx.append(y)
        clean_midpoints.append(om.class_midpoints[om.classes[y]])
        clean_logit_diffs.append(_logit_diff(clean_logits, y))

        high_logits = _class_logits(loaded, om, trial, layer, position, vector, alpha)
        high_winner = int(high_logits.argmax())
        high_midpoints.append(om.class_midpoints[om.classes[high_winner]])
        high_logit_diff_changes.append(_logit_diff(high_logits, y) - clean_logit_diffs[-1])
        high_changed.append(high_winner != y)

        low_logits = _class_logits(loaded, om, trial, layer, position, vector, -alpha)
        low_winner = int(low_logits.argmax())
        low_midpoints.append(om.class_midpoints[om.classes[low_winner]])
        low_logit_diff_changes.append(_logit_diff(low_logits, y) - clean_logit_diffs[-1])
        low_changed.append(low_winner != y)

    high_deltas = [h - c for h, c in zip(high_midpoints, clean_midpoints)]
    low_deltas = [l - c for l, c in zip(low_midpoints, clean_midpoints)]

    return {
        "layer": layer,
        "position": position,
        "alpha": alpha,
        "clean_midpoints": clean_midpoints,
        "clean_logit_diffs": clean_logit_diffs,
        "high": _direction_summary(high_deltas, high_logit_diff_changes, high_changed),
        "low": _direction_summary(low_deltas, low_logit_diff_changes, low_changed),
    }


# --- AC (answer-colon): a fundamentally different mechanism -----------------
#
# AC lives in the *Phase-0* prompt (guidebook §2.6: "Last token of the Phase 0
# prompt... its final-layer residual stream produces the first answer token's
# logits") -- a different forward pass entirely from the Phase-1 self-report
# prompt every position above reads from. By the time a `Trial` exists at
# all, Phase 0 is already over and `trial.response` is fixed text; Phase 1
# never continues Phase 0's own residual stream (§2.4: re-inserting the
# answer as *text* is what makes the two phases independent, cacheable
# forward passes in the first place). So intervening at AC cannot reach the
# confidence read directly the way PANL/PANL+1/FCC/CC can -- the *only*
# channel available is changing what answer gets generated in the first
# place, which means testing AC requires a real regeneration (`generate()`,
# not a single forward pass) for every test trial, at every layer, in both
# directions. That is a categorically higher cost than every other position
# here, which is exactly why the guidebook's own null-result expectation
# (§4.6: "AC: Null — indistinguishable from PANL+1") argues for keeping this
# to a small, separate check rather than folding it into the same dense
# per-layer, dual-alpha sweep the other four positions use.


def residual_at_ac(loaded, trial, layer: int) -> torch.Tensor:
    """AC's residual-stream activation, output of decoder layer ``layer`` —
    captured from the *same* Phase-0 prompt construction
    `generation.generate_trial` used to actually produce ``trial`` (its
    ``inquiry.question``), not the Phase-1 self-report prompt every other
    `residual_at_*` function in this module reads from. A single forward
    pass, no generation needed just to capture the activation."""
    body = _phase0_prompt(trial.inquiry.question)
    templated = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": body}], tokenize=False, add_generation_prompt=True
    )
    text = templated + ANSWER_CUE
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    index = enc["input_ids"].shape[1] - 1

    captured: dict[str, torch.Tensor] = {}

    def hook(module, inputs, output):
        captured["activation"] = output[0, index].detach().clone()

    handle = loaded.model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.no_grad():
            loaded.model(**enc)
    finally:
        handle.remove()
    return captured["activation"]


def build_ac_steering_vector(
    loaded, om: LikertOM, extraction_trials: list, layer: int, top_n: int = 5,
    correctness: GroundTruth | None = None,
) -> torch.Tensor:
    """Same construction as `build_steering_vector` (rank ``extraction_trials``
    by ``om``'s own self-report, optionally correctness-filtered, top-/
    bottom-``top_n`` by that ranking) but captures activations via
    `residual_at_ac` — i.e. during the trials' own original Phase-0 answer
    generation — instead of at a Phase-1 position."""
    pool = extraction_trials
    if correctness is not None:
        pool = _filter_by_gt(pool, correctness)
        if len(pool) < 2:
            raise ValueError(
                f"only {len(pool)}/{len(extraction_trials)} extraction trials kept after filtering "
                f"by {correctness.name} -- too few to build a steering vector"
            )

    midpoints = [
        om.observe(loaded, om.build_prompt(compose_self_report_inquiry(t)))[1]
        for t in tqdm(pool, desc=f"{om.name}: ranking AC extraction pool", leave=False)
    ]
    order = sorted(range(len(pool)), key=lambda i: midpoints[i])
    top_n = max(1, min(top_n, len(pool) // 2))
    low_idx, high_idx = order[:top_n], order[-top_n:]

    activations = [
        residual_at_ac(loaded, t, layer)
        for t in tqdm(pool, desc=f"{om.name}: capturing AC activations @ L{layer}", leave=False)
    ]
    mean_norm = torch.stack([a.norm() for a in activations]).mean()

    high = torch.stack([activations[i] for i in high_idx]).mean(dim=0)
    low = torch.stack([activations[i] for i in low_idx]).mean(dim=0)
    v = high - low
    return v / v.norm() * (0.03 * mean_norm)


def _generate_with_ac_steering(
    loaded, trial, layer: int, vector: torch.Tensor, alpha: float, max_new_tokens: int = 200,
) -> str:
    """Re-runs Phase-0 generation for ``trial.inquiry.question`` with
    ``alpha * vector`` added to the residual stream at AC, output of decoder
    layer ``layer`` — returns the new response string generated under
    intervention. Unlike every other steered read in this module, this
    calls ``generate()`` (autoregressive, KV-cached), not a single forward
    pass: the hook only ever touches a real prompt position during the
    *first* (prefill) step, where the full sequence is still present in
    ``output``; every later decode step's ``output`` is a single new token
    (shape ``(batch, 1, dim)``), so the ``output.shape[1] > index`` guard
    below is required — without it, indexing at ``index`` on those later
    steps would either error or (index 0 only) corrupt a just-generated
    token instead of leaving decoding alone.
    """
    body = _phase0_prompt(trial.inquiry.question)
    templated = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": body}], tokenize=False, add_generation_prompt=True
    )
    text = templated + ANSWER_CUE
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    index = enc["input_ids"].shape[1] - 1

    def hook(module, inputs, output):
        if output.shape[1] > index:
            output[0, index] = output[0, index] + alpha * vector.to(output.dtype).to(output.device)
        return output

    handle = loaded.model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.no_grad():
            out = loaded.model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=loaded.tokenizer.pad_token_id,
                stop_strings=["\n\n"],
                tokenizer=loaded.tokenizer,
            )
    finally:
        handle.remove()
    new_tokens = out[0, enc["input_ids"].shape[1] :]
    return loaded.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def ac_steering_effect(
    loaded, om: LikertOM, extraction_trials: list, test_trials: list, layer: int, alpha: float,
    top_n: int = 5, correctness: GroundTruth | None = None, max_new_tokens: int = 200,
) -> dict:
    """The AC analogue of `steering_effect`: build the vector from
    `extraction_trials` (via `build_ac_steering_vector`), then for every
    trial in ``test_trials``, *regenerate* its answer under high- and
    low-direction AC steering (`_generate_with_ac_steering`) — an
    intervened-but-otherwise-ordinary `Trial` (same seed/inquiry, new
    response text) — and read ``om``'s *plain, unsteered* self-report (CC
    position, no hook) on that reconstructed trial, comparing against the
    original clean trial's own plain self-report. This is the only channel
    an AC intervention has to reach the confidence read at all (see the
    section docstring above) — there is no direct-forward-pass steered read
    the way PANL/PANL+1/FCC/CC have.

    Reports the same shape as `steering_effect` (midpoint delta, logit-
    difference change with ``y`` fixed at the clean prediction, first-token
    change rate, both directions) so the two are directly comparable,
    despite the different mechanism underneath.
    """
    vector = build_ac_steering_vector(
        loaded, om, extraction_trials, layer, top_n=top_n, correctness=correctness,
    )

    clean_midpoints, clean_logit_diffs = [], []
    high_midpoints, high_logit_diff_changes, high_changed = [], [], []
    low_midpoints, low_logit_diff_changes, low_changed = [], [], []

    for trial in tqdm(test_trials, desc=f"{om.name}: AC steering @ L{layer}", leave=False):
        # `layer=0` below is inert -- `_class_logits` only registers a hook
        # when `vector` is not None, and it's always None on these plain,
        # unsteered reads (the intervention already happened upstream,
        # during regeneration, not during this logit read).
        clean_logits = _class_logits(loaded, om, trial, 0, "CC", None, 0.0)
        y = int(clean_logits.argmax())
        clean_midpoints.append(om.class_midpoints[om.classes[y]])
        clean_logit_diffs.append(_logit_diff(clean_logits, y))

        high_response = _generate_with_ac_steering(loaded, trial, layer, vector, alpha, max_new_tokens)
        high_trial = dataclasses.replace(trial, response=high_response)
        high_logits = _class_logits(loaded, om, high_trial, 0, "CC", None, 0.0)
        high_winner = int(high_logits.argmax())
        high_midpoints.append(om.class_midpoints[om.classes[high_winner]])
        high_logit_diff_changes.append(_logit_diff(high_logits, y) - clean_logit_diffs[-1])
        high_changed.append(high_winner != y)

        low_response = _generate_with_ac_steering(loaded, trial, layer, vector, -alpha, max_new_tokens)
        low_trial = dataclasses.replace(trial, response=low_response)
        low_logits = _class_logits(loaded, om, low_trial, 0, "CC", None, 0.0)
        low_winner = int(low_logits.argmax())
        low_midpoints.append(om.class_midpoints[om.classes[low_winner]])
        low_logit_diff_changes.append(_logit_diff(low_logits, y) - clean_logit_diffs[-1])
        low_changed.append(low_winner != y)

    high_deltas = [h - c for h, c in zip(high_midpoints, clean_midpoints)]
    low_deltas = [l - c for l, c in zip(low_midpoints, clean_midpoints)]

    return {
        "layer": layer,
        "position": "AC",
        "alpha": alpha,
        "clean_midpoints": clean_midpoints,
        "clean_logit_diffs": clean_logit_diffs,
        "high": _direction_summary(high_deltas, high_logit_diff_changes, high_changed),
        "low": _direction_summary(low_deltas, low_logit_diff_changes, low_changed),
    }
