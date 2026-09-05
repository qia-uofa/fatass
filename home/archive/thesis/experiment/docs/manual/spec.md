# Requirements Spec — *How do LLMs Compute Verbal Confidence?* Reproduction

Checklist-style requirements for validating a completed reproduction attempt. Not a how-to guide.

---

## 0. Shared Setup (applies to all experiments)

### 0.1 Environment / dependencies

- Python >= 3.10, torch >= 2.3 (CUDA build matching driver), transformers >= 4.50 (Gemma3ForCausalLM + Magistral support), accelerate, datasets, scikit-learn >= 1.3, numpy, scipy, pandas, matplotlib, openai (GPT-4o-mini grading), tqdm.
- `torch.set_grad_enabled(False)` globally (no LM training).
- Fixed seeds for all sampling (trial selection, donor matching, CV folds).
- Greedy decoding (temperature = 0) everywhere.
- `model.eval()`, inference mode, no gradients, for all three models.
- Default fast attention (SDPA/FlashAttention) except Experiment 8 (attention blocking), which requires `attn_implementation="eager"`.
- Magistral loaded with `attn_implementation="eager"` always (needs attention access).
- Gemma 3 requires HF license acceptance + `huggingface-cli login`.
- Hardware minimums: Gemma 3 27B IT — bf16, ~54GB, 1×H100 80GB or 2×A100 40GB (`device_map="auto"`); Qwen 2.5 7B Instruct — bf16, ~15GB, 1×A100 40GB / 1×RTX 6000 Ada; Magistral Small 2506 24B — bf16, ~48GB, 1×H100 80GB or 2×A100 40GB. Reserve ≥20GB extra headroom + batch size 1–4 for eager-attention (attention-blocking) runs.

### 0.2 Models under test

| Role | HF checkpoint | Layers | Prompt(s) used |
|---|---|---|---|
| Primary | `google/gemma-3-27b-it` | 62 (0–61) | Categorical, numeric 0–100, minimal numeric 0–9 |
| Architecture generalization | `Qwen/Qwen2.5-7B-Instruct` | 28 (0–27) | Categorical only |
| Reasoning-model generalization | `mistralai/Magistral-Small-2506` | 40 | Categorical (with CoT trace) |
| Grader/auxiliary judge | `gpt-4o-mini` (OpenAI API) | — | Correctness grading; hedging-language check |

Common settings: greedy decoding; Magistral `max_new_tokens=1024`; numeric-confidence prompt `max_new_tokens=4`.

Categorical-prompt efficiency requirement: verify the 10 class-initial tokens are pairwise distinct (assertion script in §0.5); if so, a single forward pass (next-token logits at final prompt position) suffices — no generation needed for confidence elicitation.

Pre-intervention sanity gate (required before any intervention experiment): on a held-out sample, (a) forward-pass argmax next-token must match `model.generate()` output, and (b) that token must be one of the 10 valid class-initial tokens. Filter out failing trials.

### 0.3 Datasets

**TriviaQA (primary)**
- Config: `rc.nocontext` (closed-book, no supporting document), HF `datasets` hub.
- Preprocessing: deduplicate on normalized question text (required).
- Split: validation (recommended default; not stated in paper).
- Sample sizes: Gemma categorical behavioral run n=7,858; Gemma numeric (0–100) n=8,008; Gemma minimal-numeric (0–9) n=2,000 (separate set); activation-collection set n=3,000; Magistral behavioral run n=5,000 → 4,998 after filtering; Magistral activation set n=3,000 (stratified).
- Correctness labels: GPT-4o-mini grader, deterministic (temp 0), single call, inputs = question + gold answer aliases + model answer, output = bare `CORRECT`/`INCORRECT` token. Cache all grades to disk.

**Big-Math (generalization)**
- Source: Albalak et al. 2025, arXiv:2502.17387, HF hub.
- Used with: Gemma 3 27B + categorical prompt only.
- Correctness: exact numeric/symbolic answer matching (no LLM grader).
- Target accuracy anchor: 40.2% (sample to match this; dataset is difficulty-stratified).

**MMLU (generalization)**
- Source: Hendrycks et al. 2021, HF hub, multiple-choice.
- Split: test (recommended default).
- Used with: Gemma 3 27B + categorical prompt only.
- Correctness: exact match on chosen option letter.
- Target accuracy anchor: 76.8%.

**Disjointness requirement:** partition the deduplicated TriviaQA pool once, up front, into mutually disjoint sets:
1. Activation-collection set — 3,000 trials (steering-vector extraction, probe training, OOD natural-variability stats).
2. Calibration set — 100 trials (50 high-confidence + 50 low-confidence), disjoint from all test sets (used for patching corruption means and noising means).
3. Per-experiment test sets (steering 200/layer/position; patching 200; noising 400/layer/position; swap 400+400; attention blocking 500).
Steering vectors are extracted from the 3,000-trial activation set; steering is tested on a separate question set.

### 0.4 Two-phase protocol (required for every trial)

- **Phase 0 (answer generation):** confidence instructions moved to the start of the prompt; model generates its own answer. Must record: answer string, per-token log-probs of the generated sequence, mapped answer token span, Phase-0 confidence class. Last token of Phase-0 prompt = answer-colon (AC).
- **Phase 1 (confidence elicitation):** re-present question with the model's own Phase-0 answer (never gold answer, never re-sampled) inserted per §0.5 templates; single forward pass; confidence read from final-position logits.

### 0.5 Prompts — reproduce verbatim (character-for-character)

1. **Main categorical prompt** (Gemma 3 27B, Qwen 2.5 7B) — Fig. 8 template, ends at `**Confidence**:`. Modified from Yoon et al. 2025 so every one of the 10 class first-tokens is unique. Verification requirement:
```python
CLASSES = ["No chance","Really unlikely","Chances are slight","Unlikely",
           "Less than even","Better than even","Likely","Very good chance",
           "Highly likely","Almost certain"]
first_ids = [tok(" " + c, add_special_tokens=False).input_ids[0] for c in CLASSES]
assert len(set(first_ids)) == 10
```
   Determine empirically whether the model emits the space-prefixed or bare variant and use it consistently.
   Class→midpoint mapping (used as numeric confidence everywhere): No chance 0.05, Really unlikely 0.15, Chances are slight 0.25, Unlikely 0.35, Less than even 0.45, Better than even 0.55, Likely 0.65, Very good chance 0.75, Highly likely 0.85, Almost certain 0.95.
   High-confidence band = {Highly likely, Very good chance, Almost certain}. Low-confidence band = {No chance, Really unlikely, Chances are slight}.
2. **Full numeric prompt (0–100)** (Gemma 3 27B) — Fig. 15 template, instructs no leading space before first digit (keeps first generated token a bare digit).
3. **Minimal numeric prompt (0–9)** (attention blocking only) — Fig. 16 template, single-token answer, minimal template tokens between PANL and CC, includes trailing apostrophe.
4. **Magistral Phase 1 (CoT)** — Fig. 24 template, `max_new_tokens=1024`, greedy.
5. **Magistral Phase 2 (confidence w/ trace)** — Fig. 23 template; full reasoning trace + extracted answer inserted; categorical confidence instructions follow.
6. **CoT suppression requirement:** all main experiments include `(NO REASONING OR EXPLANATION)`; do not allow reasoning at the confidence stage.
7. **Underdetermined — chat template:** apply each model's chat template (all are `-it`/`-Instruct`), prompt as a single user turn; must be applied consistently since it shifts position indices.

### 0.6 Token positions (must be located per-trial by tokenization, never hard-coded offsets)

| Abbrev. | Definition |
|---|---|
| AC | Last token of Phase-0 prompt (colon of `**Answer**:`) |
| first A | First token of model's answer |
| last A | Final token of model's answer (excluded from main analyses — confounded with content) |
| PANL | `\n` immediately after `**Answer**: {answer}` (Magistral: newline terminating response block) |
| PANL+1 | Token immediately after PANL |
| FCC | Colon preceding `$CLASS` in instruction block |
| CC | Very last token of the prompt (final `**Confidence**:` colon) |
| QTT | Third token of the question (probing control) |
| Trace k% | Magistral only: 10 CoT trace positions at 10% increments |

Requirement: verify the post-answer newline is a single token in each tokenizer, not merged with adjacent characters — must hold for Gemma, Qwen, and Mistral tokenizers.

### 0.7 Trial pools

- Gemma/Qwen categorical H/L bands: high = top-3 classes, low = bottom-3 classes (Gemma); Qwen adjustment: low = "Unlikely", high = "Likely".
- Steering test: 200 trials/layer/position, half from top-3, half from bottom-3 classes.
- Steering vector extraction: 25 highest ("Almost certain") + 25 lowest ("No chance") trials from the activation-collection set, restricted to trials answered correctly.
- Patching: 200 high-confidence trials (top-3 classes, by Phase-0 report).
- Noising: 400 trials/layer/position (all trials, not confidence-restricted); calibration set 100 (50H+50L).
- Swap: 400 high-confidence recipients + 400 low-confidence recipients; low pool has only N=221 available → sample with replacement to 400.
- Magistral adjustment: 92% of reports are "Almost certain"; draw from distribution extremes sorted by midpoint; activation set retains all trials with confidence ≤0.7, fills remainder by random sampling from high-confidence trials.

### 0.8 Metrics — exact definitions

1. **Logit difference:** Δ_logit = z_y − mean(z_k, k≠y), over the 10 class-initial token IDs only, y = clean-run predicted class. Report as **logit-difference change** = intervened Δ_logit − clean Δ_logit (target class y fixed at clean prediction).
2. **Confidence / confidence change:** confidence = midpoint of predicted class's range (§0.5 table); change = intervened − clean. Numeric prompt: confidence = generated integer 0–100; change = integer difference.
3. **First token change rate:** fraction of trials where intervened argmax class token ≠ clean argmax class token (numeric prompt: first-digit change rate).
4. **Percent recovery** (patching only): Recovery_M = (M_patched − M_corrupt)/(M_clean − M_corrupt) × 100%. For first-token change rate (lower = better), invert: Recovery = (Rate_corrupt − Rate_patched)/Rate_corrupt × 100%.
5. **Calibration:** ECE — 10 bins (10 classes for categorical; 10 equal-width bins for numeric), no temperature scaling / no post-hoc recalibration. AUROC — confidence score vs. binary correctness.
6. **Error bars:** SEM across trials on all plots; treat an effect as present only when it separates from the PANL+1 control by non-overlapping SEM bars.

### 0.9 Layer sweeps

- Gemma 3 27B (62 layers): `0, 10, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 40, 50, 61`.
- Qwen 2.5 7B (28 layers): dense, all layers 0–27.
- Magistral (40 layers): dense, all 40 layers.
- Attention blocking (§Exp.8): different convention, see below.

### 0.10 Intervention mechanics (required for Experiments 1–4, 7)

- Hook point: output of the decoder layer, i.e. after the MLP block (residual-stream output) — applied uniformly across all residual-stream interventions.
- Steering: `h_steered = h + alpha * v`, where `v` normalized then scaled to 3% of mean residual L2 norm at that (layer, position) over the activation-collection set.
- Replace/patch/noise/swap: direct replacement of the residual-stream vector at one (layer, position).
- Patching corruption is at the input-embedding level (`inputs_embeds`), before layer 0, so it propagates through the full forward pass.
- Clean activations must be cached (CPU, float16) for patching/swapping: per-trial, per-layer, per-position.

---

## 1. Experiment 0 — Behavioral baseline and calibration

**Requirements**
- Models/prompts: Gemma 3 27B categorical (n=7,858), Gemma numeric 0–100 (n=8,008), Gemma minimal-numeric 0–9 (n=2,000, separate set), Qwen categorical (same TriviaQA subset as Gemma), Gemma+BigMath categorical, Gemma+MMLU categorical, Magistral categorical (n=5,000 → 4,998 after filtering).
- Phase 0 + Phase 1 run per §0.4; grade all answers with GPT-4o-mini.
- Compute: accuracy, ECE (10 bins, no temp scaling), AUROC (confidence vs. correctness), class-histogram.
- Auxiliary check: GPT-4o-mini hedging-language classifier (yes/no, temp 0) run on all Phase-0 answer strings; expected ~0% hedging rate.

**Validation targets**

| Model / prompt | n | Accuracy | ECE | AUROC |
|---|---|---|---|---|
| Gemma categorical, TriviaQA | 7,858 | 77.4% | 0.12 | 0.71 |
| Gemma numeric 0–100, TriviaQA | 8,008 | — | 0.16 | 0.73 |
| Gemma minimal numeric 0–9, TriviaQA | 2,000 | — | 0.17 | 0.68 |
| Qwen categorical, TriviaQA | same subset | — | 0.06 | 0.65 |
| Gemma categorical, BigMath | — | 40.2% | — | — |
| Gemma categorical, MMLU | — | 76.8% | — | — |
| Magistral categorical, TriviaQA | 4,998 | — | "reasonably well calibrated" | — |

Additional targets: mean length-normalized answer log-prob AUROC for correctness = 0.75 (must exceed verbal-confidence AUROC of 0.71). Magistral: 92% of reports = "Almost certain".

Baseline confidence values (zero-point for later Δconfidence plots): Gemma categorical steering set (n=200) = 0.55; Gemma categorical Fig.22 summary set = 0.48; Gemma numeric = 0.54; Qwen categorical = 0.56.

Gate: Experiment 0 must replicate (ECE 0.12, AUROC 0.71, accuracy 77.4% for Gemma categorical) before proceeding to intervention experiments.

---

## 2. Experiment 1 — Activation steering

**Requirements**
- Steering vectors: v_high = μ(H)−μ(L) per (layer, position), from 25 highest/25 lowest correctly-answered trials in the 3,000-trial activation set; v_low = −v_high.
- Normalization: v/‖v‖ × 0.03 × mean_residual_norm_at_layer; apply `h + alpha*v` at output of decoder layer.
- Strengths: α ∈ {2, 5} for main figures; α ∈ {1, 10} additionally reported (Fig. 29).
- Positions: PANL, CC (primary); PANL+1, FCC (controls); first answer token, last answer token (reported separately); AC (Experiment 7).
- Trials: 200/layer/position, half from top-3 classes, half from bottom-3.
- Layers: §0.9 sweep. Full grid: 4 positions × 2 directions × 2 scales × 22 layers × 200 trials.
- Metric: Δ confidence (steered midpoint − clean midpoint), SEM error bars.

**Validation targets**

| Position | Peak layers | Δ confidence (α=5) |
|---|---|---|
| PANL | 21–25 | high ≈ +0.15 to +0.20; low ≈ −0.20 |
| CC | 30–35 (extends to ~40–61) | high ≈ +0.40; low ≈ −0.40 |
| PANL+1 | — | ≈ ±0.02 |
| FCC | — | ≈ ±0.02 |
| First answer token | — | null |
| AC | — | null (≈ PANL+1) |

Baseline confidence: 0.55.

Cross-model peak layers: Gemma categorical PANL L25 / PANL+1 L28 / CC L30. Gemma numeric PANL L25 / PANL+1 L31 / CC L31. Qwen categorical PANL L15 / PANL+1 L1 / CC L22.

---

## 3. Experiment 2 — Activation patching (corrupt-then-restore)

**Requirements**
- Corruption: mean-ablate answer-token input embeddings using per-position means from a 100-trial calibration set (50H+50L, disjoint from test set); mean computed per answer-position index across calibration trials with ≥ that many answer tokens.
- Patch: restore clean activation at exactly one (position, layer) after MLP block; all other positions retain corrupted activations.
- Positions: PANL, CC, PANL+1 (control).
- Layers: §0.9 sweep.
- Trials: 200 high-confidence trials (top-3 classes, by Phase-0 report).
- Baselines required: clean (no corruption/patch), corrupt (corruption, no patch).
- Metrics: logit difference, confidence, first-token change rate, plus percent recovery for each.

**Validation targets**

- Clean logit diff ≈ 11.5; corrupt logit diff ≈ 0; corrupt first-token change rate = 100% (validation gate — must hold before proceeding).

| Position | Logit-diff recovery | Confidence recovery | Token-change recovery | Peak layer |
|---|---|---|---|---|
| PANL | partial (Δlogit → ≈2.3; ~20%) | partial (→ ≈0.40; ~24.3% at L25) | 100%→≈78% | L25 |
| CC | near-complete (→ ≈12 by L61) | near-complete (≈0.85) | 100%→≈5% | rises after L30, peaks L40–61 |
| PANL+1 | ≈0 | ≈0 (−1.4% recovery) | ≈0 | none |

Cross-model peak layers: Gemma categorical PANL L25/PANL+1 L0/CC L61; Gemma numeric PANL L25/PANL+1 L0/CC L40; Qwen PANL L15/PANL+1 L27/CC L27.

---

## 4. Experiment 3 — Activation noising (mean ablation)

**Requirements**
- Replace residual-stream activation with mean from a balanced 100-trial calibration set (50 top-3-class, 50 bottom-3-class), disjoint from test set.
- Positions: PANL, CC, PANL+1 (control). One layer at a time, §0.9 sweep.
- Trials: n=400/layer/position (all trials, not confidence-restricted).
- Primary metrics: logit-difference change, first-token change rate (confidence change not primary here).

**Validation targets**

Clean logit diff ≈ 9.4.

| Position | Logit diff after noising | First-token change rate | Peak layer |
|---|---|---|---|
| PANL | ≈8.4 (~11% reduction) | peaks ≈14% | L25–26 |
| CC | falls to ≈2.8 by L61 | rises to ≈78% | rises after L30, max L61 |
| PANL+1 | flat ≈9.4 | flat ≈3–4% | none |

Cross-model peak layers: Gemma categorical PANL L25/PANL+1 L15/CC L61; Gemma numeric PANL L26/PANL+1 L26/CC L61; Qwen PANL L11/PANL+1 L6/CC L21.

---

## 5. Experiment 4 — Activation swap (interchange intervention)

**Requirements**
- 2×2 factorial: recipient confidence (high/low) × donor confidence (high/low) → conditions H→H, L→L (same-confidence controls), H→L, L→H (cross-confidence).
- Recipient sets fixed within regime: same 400 high recipients for H→H/H→L; same 400 low recipients for L→L/L→H.
- Partition by clean confidence report: high = top-3 classes (N>400 available); low = bottom-3 classes (N=221 available → sample with replacement to 400).
- Donor–recipient matching (required): match on tokenized question length and answer length via quantile bins (10 bins/axis, recommended default). Target matching quality to reproduce/report: question-length bins matched 100%; answer-length bins matched 94–100%; mean |ΔL_Q| ≈1.5–2.7 tokens; mean |ΔL_A| ≈0.3–0.5 tokens.
- Procedure: cache donor's clean residual stream at (layer, position); replace recipient's activation at that (layer, position); compute metrics vs. recipient's clean run.
- Positions: PANL (main), CC, PANL+1 (control). Layers: §0.9 sweep.

**Validation targets (PANL, peak layer 26)**

| Condition | Confidence change | Logit-diff change | Token change rate |
|---|---|---|---|
| L→H | ≈+0.21 | ≈−1.2 | ≈37% |
| H→L | ≈−0.08 to −0.10 | ≈−2.0 (largest) | ≈30% |
| H→H (control) | ≈0 | ≈−1.1 | ≈15% |
| L→L (control) | ≈0 | ≈−0.3 | ≈12% |

CC: same pattern, later layers. PANL+1: null.

Asymmetry requirement: on MMLU and Magistral, L→H dominates (H→L near ceiling) — expected pattern, not a failed replication.

Cross-model peak layers: Gemma categorical PANL L26/PANL+1 L31/CC L61; Gemma numeric PANL L26/PANL+1 L31/CC L61; Qwen PANL L15/PANL+1 L15/CC L27.

---

## 6. Experiment 5 — Out-of-distribution control analysis

**Requirements (mandatory, not optional)**
- Natural pairwise variability: from the 3,000-trial activation set, ≥100,000 random trial pairs per (layer, position); compute cosine similarity and L2-norm ratio; take p5/p95.
- Per intervention type, compute the same two quantities between perturbed and unperturbed activation at layer 25:
  - Steering: clean vs. steered.
  - Patching: clean-cached vs. corruption-propagated ("pre-patch").
  - Noising: clean vs. mean-replacement.
- Compare at both PANL and PANL+1.

**Validation targets (Layer 25)**

Natural distribution: cosine [p5,p95] = [0.997–0.998, 1.000]; norm ratio [p5,p95] = [0.90, 1.10–1.11].

| Intervention | Position | Condition | Cosine sim | Norm ratio |
|---|---|---|---|---|
| Steering | PANL | High α=2 | 0.999 | 0.96 |
| Steering | PANL | Low α=2 | 0.999 | 1.04 |
| Steering | PANL | High α=5 | 0.992–0.999 | 0.91–1.04 |
| Steering | PANL | Low α=5 | 0.994–0.998 | 0.96–1.10 |
| Steering | PANL+1 | all four | 0.993–0.999 | 0.91–1.10 |
| Patching | PANL | causal | 0.999 | 0.94 |
| Patching | PANL+1 | control | 0.999 | 0.98 |
| Noising | PANL | causal | 0.999 | 0.995 |
| Noising | PANL+1 | control | 0.999 | 0.999 |

Requirement: all cosine sims > 0.99, all norm ratios within 0.91–1.10, for every intervention type — with PANL and PANL+1 drift statistically indistinguishable despite opposite causal effects (Exp. 2 recovery: PANL 24.3% vs PANL+1 −1.4%).

---

## 7. Experiment 6 — Linear probing and variance partitioning

**Requirements**
- Data: 3,000-trial activation-collection set.
- Positions: PANL, PANL+1, CC, FCC, intermediate tokens (first token of each of the 10 confidence classes as they appear in the instruction block), QTT (control), AC.
- Layers: full sweep 0–61 (dense).
- Probe targets: (a) answer correctness (binary) via L2-regularized logistic regression (scikit-learn default C=1.0), metric AUROC; (b) verbal confidence midpoint (continuous) via Ridge regression (α=1.0), metric R².
- Protocol: 5-fold CV (`KFold(n_splits=5, shuffle=True, random_state=0)`), all activations z-scored before fitting (`StandardScaler` in pipeline), report cross-validated metrics.
- Log-prob baselines (6, computed from Phase-0 per-token log-probs restricted to answer span): length-normalized mean, minimum, maximum, variance, log-prob of first answer token, log-prob of last answer token.
- Variance partitioning: for each (layer, position), fit R²_act (activations alone), R²_base (log-prob baselines alone — individually and all-six-combined), R²_both (concatenated); R²_unique = max(0, R²_both − R²_base). Run against each baseline individually and against all six combined (5-fold CV, α=1.0, all features z-scored).
- Auxiliary correlations: length-normalized log-prob vs. Phase-0 confidence; vs. Phase-1 confidence; Phase-0 vs. Phase-1 confidence (stability).
- AC-specific methodological requirement (shared with Exp. 7 decoding): select best Ridge α on the AC position, reuse the same α for PANL/PANL+1.

**Validation targets**

| Position | Correctness AUROC (peak) | Confidence R² (peak) |
|---|---|---|
| PANL | 0.80–0.83, ~0.75 by L15–20 (earliest) | ≈0.45 (≈0.75 in AC-comparison analysis) |
| CC | 0.80–0.83, late onset | ≈0.80 (highest, late layers) |
| PANL+1 | ≈0.80 | 0.35–0.45 |
| FCC | ≈0.80 | ≈0.45 |
| Intermediate tokens | 0.75–0.83 | 0.3–0.6 |
| QTT (control) | ≈0.50 (chance) — must be null | ≈0.00 — must be null |
| AC | — | ≈0.2 |

Reference lines: verbal confidence as correctness predictor AUROC=0.71; mean answer log-prob as correctness predictor AUROC=0.75.

| Quantity | Value |
|---|---|
| Mean log-prob → confidence (cross-run) | r=0.29, R²_CV=0.084 |
| Mean log-prob → confidence (within-run, Phase 0) | r=0.23, R²_CV=0.049 |
| All six log-prob baselines combined → confidence | r=0.32, R²_CV=0.100 |
| PANL activations at L40, R²_unique beyond all six baselines | 0.380 |
| Phase-0 vs Phase-1 confidence consistency | r=0.63, R²_CV=0.40 |

Individual baseline R²_CV: min 0.101, mean 0.084, first 0.070, variance 0.051, last 0.039, max 0.025, all-six-combined 0.100.

R²_unique curves: PANL rises from ~L20, peaks ≈0.38–0.45 at ~L40, declines slightly; CC rises from ~L30 to ≈0.65 at L55–61.

---

## 8. Experiment 7 — Answer-colon (AC) control experiments

**Requirements**
- Run all four analyses at AC, on the same trials used for the corresponding PANL analyses:
  1. Steering at AC — identical protocol to Exp. 1.
  2. Patching at AC — corrupt AC token in addition to answer tokens (since AC precedes the answer and is otherwise left clean by answer-only corruption); compare patch-at-AC vs patch-at-PANL.
  3. Noising at AC — identical protocol to Exp. 3.
  4. Linear decoding at AC — layerwise 5-fold CV Ridge R² for verbal confidence at AC, PANL, PANL+1; select best α on AC, reuse for PANL/PANL+1 (biases comparison in AC's favor).

**Validation targets**

| Analysis | AC | PANL (same trials) |
|---|---|---|
| Steering | no significant confidence change | substantial |
| Patching | no recovery | partial recovery |
| Noising | no disruption (≈ PANL+1) | partial disruption |
| Decoding (Ridge R²) | ≈0.2 across layers | ≈0.75 |

---

## 9. Experiment 8 — Attention blocking (attention knockout)

**Requirements**
- Method (Geva et al. 2023): for source position s, target position t, zero attention weight α_{t←s} across all heads, within a specified layer range. Implementation: add −∞ (`torch.finfo(dtype).min`) to pre-softmax attention scores at (t,s) entries, per layer in target range; requires `attn_implementation="eager"`. Verify post-softmax attention from t to s is numerically zero for blocked layers.
- Layer-window convention (differs from other experiments): block across a window of 12 consecutive layers centered at each x-axis point. X-axis positions: `10, 15, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 45, 50, 56`.
- Primary prompt: minimal numeric (0–9) prompt (§0.5.3) — required because the full categorical prompt's >100 intermediate tokens create redundant multi-hop routing that masks the direct CC↔PANL edge. Also run the full categorical prompt as a complementary experiment.
- Minimal-prompt calibration gate (separate n=2,000 set): ECE=0.17, AUROC=0.68 — must hold before pathway analysis.
- Minimal-prompt conditions (n=500 trials; positions PANL, PANL+1 control, CC): CC→Q+A, CC→PANL, CC→PANL+1 (control), PANL→A (all answer tokens), PANL→last_A.
- Categorical-prompt conditions (complementary): CC→NL+1, CC→NL, CC→A, CC→Q, CC→Q+A, ALL→NL, ALL→last_A, ALL→NL+last_A, ALL→last_A_keepNL, ALL→A, ALL→NL+A, ALL→A_keepNL. (`_keepNL` = pathway blocked except PANL retains attention to answer tokens.)
- Metrics: first token/digit change rate; logit-difference change (baseline token's logit minus mean logit of alternatives — 9 digits for minimal prompt, 9 classes for categorical).

**Validation targets — minimal numeric prompt**

| Pathway | First-token change rate | Logit diff change | Peak layers |
|---|---|---|---|
| CC → PANL | peaks ≈21% | ≈−0.80 | L30–36 |
| CC → Q+A | ≈10% (≈ control) | ≈−0.2 | — |
| CC → PANL+1 (control) | ≈10% | ≈0 | — |
| PANL → A | ≈20% | ≈−0.85 | L22–28 |
| PANL → last_A | ≈20% | ≈−0.75 | L22–28 |

Layer gap between PANL→A effect and CC→PANL effect: 6–8 layers.

**Validation targets — categorical prompt**

| Condition | First-token change rate | Logit diff change |
|---|---|---|
| CC→NL+1 (control) | ≈10% | ≈0 |
| CC→NL | ≈9% (null — expected, masked routing) | ≈−0.3 |
| CC→A | ≈12% | ≈−0.2 |
| CC→Q | ≈11% | ≈−0.2 |
| CC→Q+A | ≈12% | ≈−0.4 |
| ALL→NL | ≈18–20% | ≈−0.9 |
| ALL→last_A | ≈50% (fig. ≈51%) | ≈−5.3 |
| ALL→NL+last_A | ≈48% | ≈−5.3 |
| ALL→last_A_keepNL | reduced to ≈20–24% | ≈−1.6 |
| ALL→A | ≈67–70% | ≈−8.0 |
| ALL→NL+A | ≈59% | ≈−7.3 |
| ALL→A_keepNL | reduced to ≈40–51% | ≈−4.3 |

Required conclusion pattern: answer tokens → PANL (L22–28) → CC (L30–36) → unembedding (L61); CC→Q+A blocking ≈ PANL+1-control level in both prompts (JIT ruled out).

---

## 10. Experiment 9 — Generalization suite

Re-runs Experiments 1–4 (and 6 where noted) with one component substituted per axis. Invariant to check in every axis: PANL causally sufficient, distinct from PANL+1, temporally precedes CC wherever layer-wise analysis is performed.

### 10.1 Axis 1 — Numeric (0–100) prompt, Gemma 3 27B, TriviaQA

- Prompt: §0.5.2, `max_new_tokens=4`.
- Metrics (numeric analogues): confidence change = integer diff (0–100); first-digit change rate; logit diff = clean first-digit logit − mean logit of other 9 digits.
- Multi-token caveat: all interventions occur during prefill (KV-cache), so use first-digit metrics for clean causal attribution.
- Steering n = 124 trials/condition/layer (numeric-prompt figure).

**Targets:** calibration ECE=0.16, AUROC=0.73 (n=8,008); baseline confidence 0.54. Peak layers — steering PANL L25/PANL+1 L31/CC L31; patching PANL L25/PANL+1 L0/CC L40; noising PANL L26/PANL+1 L26/CC L61; swap PANL L26/PANL+1 L31/CC L61. Steering Δconfidence (0–100 scale): PANL high≈+20, low≈−7; CC high≈+37, low≈−7.

### 10.2 Axis 2 — Qwen 2.5 7B Instruct, categorical prompt, TriviaQA

- 28 layers, dense sweep 0–27; same TriviaQA subset as Gemma; 3,000 trials for activation collection.
- Trial-pool adjustment: low = "Unlikely" class, high = "Likely" class.
- Trial counts: steering 150/condition/layer; patching 200; noising 300 (200H+100L); swap 200/condition.

**Targets:** ECE=0.06, AUROC=0.65, baseline confidence 0.56. Peak layers — steering PANL L15/PANL+1 L1/CC L22; patching PANL L15/PANL+1 L27/CC L27; noising PANL L11/PANL+1 L6/CC L21; swap PANL L15/PANL+1 L15/CC L27. Steering effects weaker than Gemma; other three experiments comparable to Gemma.

### 10.3 Axis 3 — BigMath, MMLU, Gemma 3 27B categorical prompt

- Re-run patching, noising, swap (+ confidence-distribution analysis) on each dataset with the Gemma categorical protocol.

**Targets:** BigMath accuracy 40.2% (broader confidence distribution; swap shows both directions). MMLU accuracy 76.8% (primarily high-confidence; swap asymmetric, L→H dominant, H→L near ceiling; L→H trend may be visible but not necessarily significant). Both: patching at PANL recovers confidence/logit-diff while PANL+1 doesn't; noising at PANL changes first token while PANL+1 doesn't; cross-confidence swaps at PANL shift confidence beyond same-confidence controls while PANL+1 shows nothing.

### 10.4 Axis 4 — Magistral Small 2506 (24B, 40 layers), TriviaQA

- Model: `mistralai/Magistral-Small-2506`, `attn_implementation="eager"`, `max_new_tokens=1024`, greedy.
- Behavioral run: n=5,000 → N=4,998 after filtering for valid answers + valid confidence classes.
- Two-phase prompts: §0.5.4 (Phase 1, CoT answer) and §0.5.5 (Phase 2, confidence w/ trace).
- Activation set: stratified 3,000 trials — retain all trials with confidence ≤0.7, fill remainder by random sampling from high-confidence trials.
- Position definitions: PANL = newline terminating response block; PANL+1 = subsequent token; CC = last prompt token; ALT = last token of final answer; QTT = third question token (control); Trace k% = 10 positions at 10% increments across the reasoning trace (Trace 100% = last trace token).
- Common adaptations for all three causal experiments: trial selection from confidence-distribution extremes (sorted by midpoint), not uniform bands; logit-difference metric tracks the clean trial's predicted class token across all intervention conditions (fixed target), not each condition's own argmax.
- Patching: corrupt embeddings of all tokens spanning question + entire response block (reasoning trace + final answer string), excluding PANL newline and all downstream classification tokens.
- Noising: means from 100-trial calibration set (50H+50L) at PANL and PANL+1; test set n=400 (200L+200H), shuffled; CC tested as control position (not primary, due to near-ceiling).
- Swap: 400H+400L recipients from distribution extremes; donors length-matched to recipients on both question length and reasoning-trace length via 10-quantile bins per axis; swaps at PANL and PANL+1.
- Decoding: activations at 10 trace positions + 5 standard positions (PANL, PANL+1, CC, last answer token, QTT); Ridge regression, 5-fold CV R².

**Targets:**

| Analysis | Result |
|---|---|
| Patching | substantial recovery at PANL; no effect at PANL+1 (replicates Gemma) |
| Noising | no effect at PANL beyond PANL+1 control (dissociation from Gemma — expected, see failure-mode table); substantial disruption when noising at CC |
| Swap | systematic directional shifts (L→H, H→L) at PANL beyond same-confidence controls; no effect at PANL+1; L→H dominates |
| Decoding | confidence decodable from PANL (peak R² comparable to final trace token), from CC at later layers, increasingly across the trace peaking at the final trace token; QTT explains negligible variance |

---

## 11. Configuration decisions required where the source material underdetermines them

(Any choice materially affects exact numbers, not qualitative conclusions — document whichever is used.)

| # | Parameter | Required setting |
|---|---|---|
| 1 | TriviaQA split/config | `validation`, `rc.nocontext`, deduplicated on normalized question text |
| 2 | Chat template | Apply each model's chat template, prompt as single user turn; consistent across all trials |
| 3 | Leading space on class names | Empirically determined per-model, consistent across all 10 classes |
| 4 | Residual-stream hook point | Output of decoder layer (after MLP block) — all interventions |
| 5 | `mean_residual_norm_at_layer` | Mean L2 norm at that (layer, position) over activation-collection set |
| 6 | Ridge α (main probing) | 1.0; AC comparison: tune on AC, reuse for PANL/PANL+1 |
| 7 | Logistic regression C | scikit-learn default (C=1.0), L2 penalty |
| 8 | ECE binning | 10 bins |
| 9 | Natural-variability pair count | ≥100,000 random pairs from 3,000-trial set |
| 10 | Donor-matching quantile bins | 10 bins/axis |
| 11 | Statistical significance test | Paired t-test or Wilcoxon signed-rank vs. control, on matched trials, with effect sizes |
| 12 | Phase-0 prompt wording | Categorical prompt with confidence-instruction block moved to start, prompt ends at `**Answer**:` |
| 13 | BigMath subset selection | Sampled to match 40.2% accuracy anchor |
| 14 | MMLU subset/split | `test` split, sampled across all subjects, to match 76.8% accuracy anchor |
| 15 | "Intermediate token" probe positions | First token of each of the 10 confidence classes as listed in the instruction block |

---

## 12. Master validation checklist

### 12.1 Must-hold qualitative claims

| # | Claim |
|---|---|
| Q1 | Steering at PANL modulates verbal confidence, bidirectionally and gradedly |
| Q2 | Steering at PANL+1 and FCC does not |
| Q3 | PANL effects peak at earlier layers than CC effects — in steering, patching, noising, swap, and probing |
| Q4 | Patching PANL partially recovers confidence after answer corruption; PANL+1 does not |
| Q5 | Noising PANL partially disrupts confidence; PANL+1 does not |
| Q6 | Cross-confidence swaps at PANL shift confidence directionally beyond same-confidence controls |
| Q7 | Intervention-induced OOD drift is within natural variability and equal at PANL and PANL+1, despite opposite causal effects |
| Q8 | PANL activations explain large unique confidence variance beyond all six log-prob baselines |
| Q9 | Steering / patching / noising at AC are all null |
| Q10 | Blocking CC→Q+A has no effect beyond control (JIT ruled out) |
| Q11 | Blocking CC→PANL (minimal prompt) substantially disrupts confidence |
| Q12 | Blocking PANL→answer tokens disrupts confidence at earlier layers than the CC→PANL effect |
| Q13 | PANL-vs-PANL+1 dissociation holds across prompt formats, datasets, architectures |

### 12.2 Numeric targets (consolidated)

| Quantity | Target |
|---|---|
| Gemma categorical: accuracy/ECE/AUROC | 77.4% / 0.12 / 0.71 |
| Gemma numeric: ECE/AUROC | 0.16 / 0.73 |
| Gemma minimal-numeric: ECE/AUROC | 0.17 / 0.68 |
| Qwen categorical: ECE/AUROC | 0.06 / 0.65 |
| Steering peak layers, Gemma categorical (PANL/CC) | 21–25 / 30–35 |
| Steering Δconfidence at PANL (α=5) | ≈±0.15–0.20 |
| Steering Δconfidence at CC (α=5) | ≈±0.40 |
| Steering baseline confidence | 0.55 |
| Patching: clean/corrupt logit diff | ≈11.5 / ≈0 |
| Patching: corrupt first-token change rate | 100% |
| Patching peak recovery layers (PANL/CC) | L25 / >L30 |
| Patching confidence recovery at PANL(L25)/PANL+1 | 24.3% / −1.4% |
| Noising: clean logit diff | ≈9.4 |
| Noising peak (PANL/CC token-change) | ≈14% (L25–26) / ≈78% (L61) |
| Swap peak layer at PANL | L26 |
| Swap: L→H confidence change / H→L logit-diff change | ≈+0.21 / ≈−2.0 |
| OOD: cosine similarity, all interventions | >0.99 |
| OOD: norm ratio, all interventions | 0.91–1.10 |
| OOD: natural cosine [p5,p95] / natural NR [p5,p95] | [0.997,1.000] / [0.90,1.11] |
| Probing: mean-logprob AUROC for correctness | 0.75 |
| Probing: verbal-confidence AUROC for correctness | 0.71 |
| Variance partitioning: all six logprob baselines R²_CV (r) | 0.100 (r=0.32) |
| Variance partitioning: single mean-logprob baseline R²_CV | 0.084 |
| Variance partitioning: PANL L40 R²_unique | 0.380 |
| Individual baselines R²_CV (min/mean/first/var/last/max) | 0.101/0.084/0.070/0.051/0.039/0.025 |
| Logprob→confidence: within-run/cross-run | r=0.23,R²=0.049 / r=0.29,R²=0.084 |
| Phase-0 vs Phase-1 confidence consistency | r=0.63, R²_CV=0.40 |
| AC decoding R² vs PANL decoding R² | ≈0.2 vs ≈0.75 |
| Attention blocking (minimal): CC→PANL peak | ≈21%, L30–36 |
| Attention blocking (minimal): CC→Q+A / control | ≈10% / ≈10% |
| Attention blocking (minimal): PANL→A, PANL→last_A peak | ≈20%, L22–28 |
| Layer gap: PANL→A vs CC→PANL effects | 6–8 layers |
| Attention blocking (categorical): ALL→last_A → keepNL | 50% → 20–24% |
| Attention blocking (categorical): ALL→A → keepNL | 67–70% → 40–51% |
| BigMath / MMLU accuracy | 40.2% / 76.8% |
| Magistral: n after filtering / "Almost certain" share | 4,998 / 92% |

### 12.3 Diagnostic failure modes (indicates a setup error, not a real dissociation)

| Symptom | Likely cause |
|---|---|
| Corrupt baseline ≠ 100% token change | Answer-span token mapping wrong |
| PANL+1 shows effects comparable to PANL | Intervening on a slice/range instead of single position, or newline not isolable in tokenizer |
| PANL and CC peak at same layer | Position indices swapped, or not recomputed per-trial |
| All confidence classes collapse to one token id | Class-initial tokens not unique — check leading-space variant |
| Steering has no effect anywhere | Vector normalization wrong, or hook applied to wrong tuple element |
| Attention blocking has no effect anywhere | Not using `attn_implementation="eager"`, or blocking single layer instead of 12-layer window |
| CC→PANL blocking is null | Expected with categorical prompt — must use minimal numeric prompt for this test |
| Probing AUROC ≈0.5 at every position | Correctness labels misaligned, or activations captured at wrong forward pass |
| Magistral PANL noising is null | Expected — trace-distributed redundancy (see Axis 4) |

### 12.4 Compute budget reference (Gemma 3 27B main experiments)

| Experiment | Forward passes |
|---|---|
| Phase 0 generation (7,858 q) | 7,858 generations |
| Phase 1 clean (7,858 q) | 7,858 single passes |
| Activation collection (3,000) | 3,000 |
| Steering: 22 layers × 6 positions × 2 directions × 2 scales × 200 | ≈105,600 |
| Patching: 22 layers × 3 positions × 200 (+baselines) | ≈13,600 |
| Noising: 22 layers × 3 positions × 400 | ≈26,400 |
| Swap: 22 layers × 3 positions × 4 conditions × 400 | ≈105,600 |
| Attention blocking: 16 windows × 5 pathways × 500 × 2 prompts | ≈80,000 |

Total ≈350k forward passes for Gemma main experiments (excl. generation); generalization suite multiplies by ≈3–4×.
