# Health check: `vconf` vs. the paper reproduction spec

Audit of `vconf/` logic and implementation against
`docs/manual/reproduction-guidebook.md` (the implementation spec derived from
Kumaran et al. 2026, *How do LLMs Compute Verbal Confidence?*), 2026-08-30.

## What's solid

The core two-phase protocol, prompts (verified character-for-character
against §2.5), token-position logic (PANL/PANL+1/CC/FCC/AC/QTT),
sentiment/class-midpoint definitions, generic metrics (logit difference,
recovery, ECE/AUROC, first-token-change-rate), and Experiments 0–2, 3–5, and
7–8 for **Gemma categorical/numeric and Qwen** are faithfully and correctly
implemented, with disjointness requirements (activation/calibration/test
sets) actually enforced and asserted, not just assumed.

## Findings, ranked by severity

### 1. Magistral (reasoning-model axis) is a facade for three of its four required experiments

- `pipeline.run_phase0`/`run_phase1` — the shared, tested code path every
  other model uses — silently mishandles Magistral: `prompts.PHASE0_KIND["magistral"]
  = "categorical"` routes it through the generic Phase-0 prompt builder
  instead of the dedicated CoT prompt (§2.5.4), so if invoked generically it
  produces no reasoning trace at all and truncates at 64 tokens instead of
  the required 1024 (`config.py:218` vs `173`, `MAX_NEW_TOKENS_PHASE0` vs
  `MAX_NEW_TOKENS_MAGISTRAL`).
- There is no `run_phase1` analogue for Magistral either — only disconnected
  prompt-builder helpers in `exp9_generalization.py`
  (`render_magistral_phase1` builds the prompt but nothing reads class
  logits back into a trial).
- Consequently, Axis 4's actual causal experiments (patching/noising/swap/
  decoding, required by §12.4) are never run — the notebook
  (`experiment_9_generalization_suite.ipynb`, cells 17–19) stops after
  Phase-0/Phase-1 and activation-index construction. The final
  generalization summary (cell 21) literally reports `None` for "PANL beats
  control" / "PANL precedes CC" on this axis.

### 2. Axis 3 (BigMath/MMLU) is similarly incomplete

- Only an accuracy check runs (`E0.calibration(ds_trials)` in cell 15); no
  `exp2_patching`/`exp3_noising`/swap function is ever invoked for BigMath or
  MMLU, despite §12.3 requiring "re-run patching, noising, and swap ... on
  each dataset." Same `None`/`None` result in the summary table.
- Both datasets fall back to `AliasCorrectness()` (GPT-4o-mini-or-alias-match)
  instead of the dataset-specific graders the guidebook specifies (BigMath
  answer-matching, MMLU exact-match on option letter):
  `config.py:291-294`'s `preset("gemma-bigmath")`/`preset("gemma-mmlu")` set
  no `ground_truth` override, and `notebook.graded()` is called with no
  override either. For MMLU in particular, answers are already reduced to
  single letters (`data.py:96-125`), so this needlessly routes a
  deterministic exact-match comparison through an LLM judge.

### 3. Experiment 6 (probing/variance-partitioning) is short two required pieces

- §9.3 requires R²_unique computed against each of the six log-prob
  baselines individually *and* against all six combined. Only the combined
  pass (`baseline="all"`) actually runs in
  `experiment_6_probing_variance_partitioning.ipynb` cell 12; the
  per-baseline path exists in `layerwise_variance_partition`
  (`exp6_probing.py:149-178`) and is unit-tested
  (`tests/test_exp6_probing.py:87-91`) but never exercised end-to-end. Six
  required R²_unique curves are missing from the actual reproduction.
- The "intermediate tokens" probing position (first token of each
  confidence class in the instructions) is a required position (§9.1, with
  its own expected AUROC/R² range in §9.5) and is simply absent —
  `positions.py:18` only defines `AC, first A, last A, PANL, PANL+1, FCC,
  CC, QTT`, and the notebook probes only six of those, no per-class
  instruction tokens.
- Minor, same experiment: the within-run R²_CV anchor (r=0.23/R²=0.049,
  §9.4) is only ever computed as a raw Pearson r in
  `correlation_diagnostics` (`exp6_probing.py:210-237`), never
  cross-validated into an R².

### 4. Minor robustness/reproducibility gaps

- `exp8_attention_blocking.py:62-113` never asserts
  `attn_implementation == "eager"` before blocking — currently correct in
  practice (the notebook sets it manually via the `gemma-minimal` preset and
  an explicit override) but nothing guards against a silent no-op
  regression, which is exactly the failure mode §11.1 warns about (a
  fused/flash backend can silently ignore the custom attention mask).
- `exp4_swap.py:176` seeds donor tie-breaking with `hash(condition) % 1000`
  — Python's string hashing is randomized per-process by default
  (`PYTHONHASHSEED`), so exact donor assignment on quantile-bin ties is not
  reproducible run-to-run, unlike every other seed in the codebase (plain
  int seeds via `np.random.default_rng`).
- No regression test guards Experiment 6's CV/z-scoring order against a
  future leakage reintroduction. The current implementation is correct —
  `StandardScaler` + estimator combined in one `sklearn.Pipeline` passed to
  `cross_val_predict`, refitting scaling per fold — but nothing would catch
  a regression to "z-score the whole dataset, then CV."

### 5. Cosmetic / dead-code items

- Magistral's `almost_certain_share: 0.92` target in
  `exp0_behavioral.PAPER_TARGETS` (`exp0_behavioral.py:33`) is never checked
  by `validate()` (`exp0_behavioral.py:176-192` only compares keys present
  in `BehavioralResult.summary()`) — the real check lives independently in
  `exp9_generalization.py:91`. Dead/unvalidated data, not a wrong number.
- `exp2_patching.py`'s two trial selectors are internally inconsistent:
  `select_patching_trials` (lines 51-68) bands by `t.phase0_class` per
  §5.4, but `select_calibration_trials` (lines 71-87), used for the *same*
  experiment's mean-ablation calibration set, bands by `t.class_index`
  (Phase-1) instead. Not a clear-cut spec violation (the guidebook doesn't
  say which phase should gate calibration), but worth resolving explicitly.

## Outside the agents' scope, worth flagging

The working tree currently shows `GUIDE.md`, `plan.md`, and `log.md` as
deleted (unstaged) under `code_morph/`. `GUIDE.md` in particular is the
plain-language companion to the spec used for this audit
(`docs/manual/reproduction-guidebook.md`, which is untouched and still
present). If that deletion wasn't deliberate, recover with:

```
git checkout -- home/thesis/experiment/code_morph/GUIDE.md \
               home/thesis/experiment/code_morph/plan.md \
               home/thesis/experiment/code_morph/log.md
```

## Bottom line

The paper's central claim — cached retrieval at PANL, preceding CC, across
Gemma categorical/numeric and Qwen — is soundly and correctly reproduced
end-to-end. What's missing is breadth: the generalization suite's two
hardest axes (Magistral reasoning, BigMath/MMLU) are wired up only partway,
so "generalizes across datasets/architecture/reasoning models" is currently
**asserted but not actually demonstrated** by running code — only the two
axes that do work (numeric prompt, Qwen) back that claim today.

## Addendum, 2026-08-30: Gemma cannot currently execute at all

The "What's solid" section above calls Gemma categorical/numeric "correctly
implemented" — true of the code as read, but at the time of that audit
`HF_TOKEN` was empty (see "What cannot run on this machine" in `README.md`),
so none of it had ever actually been run against real `google/gemma-3-27b-it`
output. `HF_TOKEN` was populated later the same day, and a real run (via
`notebooks_benzon/phase_0_calibration`, `config.json` flipped to
`"model": "gemma"`) surfaced two issues execution-only review couldn't catch:

1. **A real, now-fixed bug**: `models.render_prompt` (`vconf/models.py:89-106`)
   assumed `tokenizer.apply_chat_template(...)` embeds a turn's content
   verbatim, and located it in the templated string with a plain substring
   search. Gemma's chat template strips 1-2 trailing whitespace characters
   from the turn content before embedding it, so the exact-match search
   failed outright (`ValueError: chat template altered the prompt body`) for
   *every* prompt this repo builds (Phase 0 ends the user turn on a bare
   newline before `**Answer**:`; Phase 1 likewise before `**Confidence**:`).
   Fixed by falling back to a stripped-content match and shifting by however
   much leading whitespace was trimmed (trailing-only trims never invalidate
   a span, since `cue_cut` never lets a recorded span reach `prefix`'s
   trailing edge) — verified directly against the real tokenizer that AC/CC
   still land on the exact last token, per §2.6.
2. **An unfixed, upstream blocker**: `google/gemma-3-27b-it` is ~54GB in
   bf16, too large for one 48GB GPU on this machine, so it needs
   `device_map="auto"` multi-GPU sharding — and every trial output whether
   attention implementation is `sdpa` (crashes with `CUDA error:
   device-side assert triggered` inside `transformers.masking_utils`) or
   `eager` (no crash, but every generation is garbage tokens, e.g.
   `<unused1155>`, mixed-script noise, no relation to the prompt). Isolated
   to `Gemma3TextModel.forward` (`transformers` 5.16.1,
   `modeling_gemma3.py:554-561`): it computes the per-layer-type
   `position_embeddings` (rotary cos/sin) and `causal_mask_mapping` **once**,
   using the hidden state on its *initial* device, then passes those same
   tensors into every decoder layer regardless of which GPU `accelerate`
   placed that layer on. Confirmed independent of attention implementation,
   batching, padding, and tokenization (a single non-batched, non-padded
   prompt still produces garbage) — `accelerate`'s dispatch hooks aren't
   correctly relocating these shared, dict-indexed structures across the
   pipeline-sharded layers. This is a `transformers`/`accelerate`
   compatibility gap, not a `vconf` bug, and not fixable via `RunConfig`.

Net effect: the `paper` profile (which requires this checkpoint) still
cannot run end-to-end here, now for a different reason than "no `HF_TOKEN`"
— every result this repo has actually validated against real model output
remains Qwen-only (`reduced` profile).
`notebooks_benzon/phase_0_calibration/config.json` stays pinned to
`"model": "qwen"` until either a working `transformers`/`accelerate`
combination is found or the checkpoint is run quantized (a numerical-fidelity
tradeoff against the paper's own bf16 setting, not attempted here).
