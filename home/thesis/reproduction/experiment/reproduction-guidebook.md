# Reproduction Guidebook

## *How do LLMs Compute Verbal Confidence?* (Kumaran, Conmy, Barbero, Osindero, Patraucean & Veličković, ICML 2026 / arXiv:2603.17839v3)

**Scope of this document.** This is a complete, self-contained protocol for reproducing every
experiment in the paper. It assumes no access to the paper itself. Everything you need —
research questions, datasets, prompts verbatim, model checkpoints, hyperparameters, intervention
algorithms, metric definitions, trial counts, and the numeric results you should reproduce — is
restated here.

**Important framing note.** The authors do not release code (none is referenced in the paper).
Everything below is an implementation-level specification derived from the paper's methods
sections; where the paper leaves a detail underdetermined, this guidebook says so explicitly and
supplies a concrete, defensible default so you can proceed. Those points are collected in
§13 ("Underdetermined details and recommended defaults") so you can audit them.

---

## Table of contents

- [1. Research questions and hypotheses](#1-research-questions-and-hypotheses)
- [2. Shared setup](#2-shared-setup)
  - [2.1 Environment and dependencies](#21-environment-and-dependencies)
  - [2.2 Models under test](#22-models-under-test)
  - [2.3 Datasets](#23-datasets)
  - [2.4 The two-phase protocol](#24-the-two-phase-protocol)
  - [2.5 Prompts (verbatim)](#25-prompts-verbatim)
  - [2.6 Token positions — the central objects of study](#26-token-positions--the-central-objects-of-study)
  - [2.7 Trial pools and how to build them](#27-trial-pools-and-how-to-build-them)
  - [2.8 Metrics](#28-metrics)
  - [2.9 Layer sweep](#29-layer-sweep)
  - [2.10 Reference hook infrastructure](#210-reference-hook-infrastructure)
- [3. Experiment 0 — Behavioral baseline and calibration](#3-experiment-0--behavioral-baseline-and-calibration)
- [4. Experiment 1 — Activation steering](#4-experiment-1--activation-steering)
- [5. Experiment 2 — Activation patching (corrupt-then-restore)](#5-experiment-2--activation-patching-corrupt-then-restore)
- [6. Experiment 3 — Activation noising (mean ablation)](#6-experiment-3--activation-noising-mean-ablation)
- [7. Experiment 4 — Activation swap (interchange intervention)](#7-experiment-4--activation-swap-interchange-intervention)
- [8. Experiment 5 — Out-of-distribution control analysis](#8-experiment-5--out-of-distribution-control-analysis)
- [9. Experiment 6 — Linear probing and variance partitioning](#9-experiment-6--linear-probing-and-variance-partitioning)
- [10. Experiment 7 — The answer-colon (AC) control experiments](#10-experiment-7--the-answer-colon-ac-control-experiments)
- [11. Experiment 8 — Attention blocking (attention knockout)](#11-experiment-8--attention-blocking-attention-knockout)
- [12. Experiment 9 — Generalization suite](#12-experiment-9--generalization-suite)
- [13. Underdetermined details and recommended defaults](#13-underdetermined-details-and-recommended-defaults)
- [14. Master validation table](#14-master-validation-table)
- [15. Suggested execution order and compute budget](#15-suggested-execution-order-and-compute-budget)

---

## 1. Research questions and hypotheses

### 1.1 The phenomenon

"Verbal confidence" means prompting an LLM to *state* its confidence that its own answer is
correct, either as a natural-language category ("Almost certain") or as a number (0–100). This is
the standard way to get uncertainty estimates out of black-box models that do not expose token
log-probabilities. The paper asks how this number is actually computed inside the network.

### 1.2 Question 1 — *When* is confidence computed?

Two competing accounts:

- **Just-in-time (JIT) hypothesis.** No confidence-specific computation happens while the answer
  is being generated. The model computes confidence only at the moment it is asked — i.e. at the
  final token of the confidence prompt — by integrating features of the question and answer *at
  that moment*.
- **Cached retrieval hypothesis.** Confidence is computed *automatically* during/just after answer
  generation, before the model has any way of knowing a confidence rating will be requested, and
  is stored ("cached") at an answer-adjacent position for later retrieval when verbalization is
  required.

**Why the distinction is testable.** Causal attention means a token cannot attend to tokens that
come after it. The post-answer newline token (PANL) sits immediately after the answer and *before*
the confidence instructions. If a dedicated confidence representation exists at PANL, the model
must have built it without knowing a confidence question was coming.

**Discriminating predictions:**

| Prediction | JIT | Cached retrieval |
|---|---|---|
| Interventions at CC (the last prompt token) affect confidence | Yes | Yes |
| Interventions at PANL affect confidence | **No** | **Yes** |
| PANL effects peak at *earlier* layers than CC effects | n/a | **Yes** |
| Blocking CC's attention to question + answer tokens destroys confidence | **Yes** | No |
| Blocking CC's attention to PANL disrupts confidence | No | **Yes** |

### 1.3 Question 2 — *What* does verbal confidence represent?

Two competing accounts, borrowed from the decision-neuroscience literature on confidence:

- **First-order account.** Confidence is a direct readout of decision-variable strength — in LLM
  terms, verbal confidence is just a summary of token log-probabilities: the same signal that
  chose the answer tokens also sets the confidence. A pure first-order architecture cannot support
  error detection, because confidence and accuracy are yoked to one signal.
- **Second-order account.** Confidence involves a *distinct* computation that evaluates the
  decision, drawing on partially independent signals — an evaluation of question–answer *fit*,
  richer than generation fluency.

**Discriminating predictions:**

| Prediction | First-order | Second-order |
|---|---|---|
| Answer log-probabilities explain most variance in verbal confidence | **Yes** | No |
| Residual-stream activations explain confidence variance *beyond* log-probs | No | **Yes** |
| Interventions at the answer-colon (AC) — the position that literally produces the first answer token — modulate verbal confidence | **Yes** | **No** |

### 1.4 The paper's answers (what you are trying to reproduce)

1. **Cached retrieval wins.** Confidence representations exist at PANL, emerge there at earlier
   layers than at CC, and are causally necessary and sufficient (partially) for verbal confidence
   output. Control positions immediately adjacent (PANL+1) show nothing.
2. **Information flow is:** answer tokens → PANL (layers ~22–28) → CC (layers ~30–36) →
   unembedding at the final layer.
3. **Second-order wins.** Six different log-probability summaries of the answer span jointly
   explain only ~10% of verbal-confidence variance; PANL activations at layer 40 explain ~38%
   *unique* variance on top of them. Interventions at AC are null.
4. **This generalizes** across prompt format (categorical/numeric), datasets (TriviaQA, BigMath,
   MMLU), architecture (Gemma 3 27B, Qwen 2.5 7B), and to a reasoning model with a long
   chain-of-thought trace (Magistral Small 24B).

---

## 2. Shared setup

All experiments share one pipeline. Build this once; every experiment is then a different
intervention layered on top of the same forward pass.

### 2.1 Environment and dependencies

**Hardware.**

| Model | Precision | Weight footprint | Minimum practical GPU |
|---|---|---|---|
| Gemma 3 27B IT | bfloat16 | ~54 GB | 1× H100 80GB, or 2× A100 40GB with `device_map="auto"` |
| Qwen 2.5 7B Instruct | bfloat16 | ~15 GB | 1× A100 40GB / 1× RTX 6000 Ada |
| Magistral Small 2506 (24B) | bfloat16 | ~48 GB | 1× H100 80GB, or 2× A100 40GB |

Add headroom for activation caching: the attention-blocking experiments require
`attn_implementation="eager"` (see below), which materializes the full attention matrix and is
substantially more memory-hungry than SDPA/FlashAttention. Reserve ≥20 GB above the weight
footprint for those runs, and reduce batch size to 1–4.

**Software.** Nothing exotic is needed; the paper uses stock Hugging Face.

```
python >= 3.10
torch >= 2.3            # CUDA build matching your driver
transformers >= 4.50    # must be new enough for Gemma 3 (Gemma3ForCausalLM) and Magistral
accelerate              # for device_map="auto" sharding
datasets                # HuggingFace dataset loading
scikit-learn >= 1.3     # LogisticRegression, Ridge, roc_auc_score, KFold, StandardScaler
numpy, scipy, pandas
matplotlib              # figures
openai                  # GPT-4o-mini grading of free-text answers + hedging check
tqdm
```

Set determinism: `torch.set_grad_enabled(False)` everywhere (no training of the LM), fixed seeds
for every sampling step (trial selection, donor matching, CV folds), and greedy decoding.

**Access.** Gemma 3 is a gated Hugging Face repository — accept the license on the model page and
authenticate (`huggingface-cli login`) before downloading.

### 2.2 Models under test

| Role | HF checkpoint | Layers | Notes |
|---|---|---|---|
| **Primary** | `google/gemma-3-27b-it` | **62** (indices 0–61) | All main-text experiments |
| Architecture generalization | `Qwen/Qwen2.5-7B-Instruct` | **28** (indices 0–27) | Categorical prompt only |
| Reasoning-model generalization | `mistralai/Magistral-Small-2506` | **40** | 24B params, CoT trace |
| Grader / auxiliary judge | `gpt-4o-mini` (OpenAI API) | — | Marks free-text answers correct/incorrect; also used to verify absence of hedging language |

**Common load and inference settings (all three models):**

- Loaded via Hugging Face `transformers`.
- `model.eval()`, inference mode, no gradients.
- **Greedy decoding, temperature = 0.**
- `attn_implementation="eager"` **required** for any experiment that reads or writes attention
  weights (i.e. Experiment 8, attention blocking). Use the default fast attention elsewhere for
  speed — but verify once that eager and non-eager produce identical argmax confidence tokens on
  a sample of trials, since numerics differ slightly.
- Magistral only: `max_new_tokens = 1024` for the reasoning phase.
- Numeric-confidence prompt only: `max_new_tokens = 4` (enough to emit e.g. `95`).

**Critical efficiency property for the categorical prompt.** Categorical confidence is fully
determined by the **first generated token**, because the prompt is engineered so that every one of
the ten confidence classes begins with a *unique* first token. Therefore you do **not** need to
generate — a **single forward pass**, reading the next-token logits at the final prompt position,
is sufficient. This is what makes the whole layer × position sweep affordable.

**Mandatory sanity check before any intervention experiment:** verify on a held-out sample that
(a) the forward-pass argmax next-token matches what `model.generate()` actually produces, and
(b) that argmax token is always one of the ten valid class-initial tokens. Filter out any trial
where this fails.

### 2.3 Datasets

#### 2.3.1 TriviaQA (primary)

- **Source:** `TriviaQA` (Joshi et al., 2017), downloaded via the Hugging Face `datasets` hub.
  Use the `rc.nocontext` / unfiltered configuration — the task here is closed-book factual recall
  with **no supporting document** given to the model. (The paper says only "downloaded via the
  HuggingFace platform"; the no-context variant is the only one consistent with the prompts shown,
  which contain a bare question and nothing else.)
- **Preprocessing:** **remove duplicates.** (Explicitly stated. TriviaQA contains repeated
  questions across its splits/sources; deduplicate on normalized question text.)
- **Split:** the paper does not name a split. Use the **validation** split, which is the standard
  choice for closed-book QA evaluation and is large enough (~11k unique questions after dedup) to
  supply every disjoint subset below.
- **Sample sizes actually used:**

| Purpose | n |
|---|---|
| Gemma categorical behavioral/calibration run | **7,858** questions |
| Gemma numeric (0–100) behavioral/calibration run | **8,008** questions |
| Gemma minimal-numeric (0–9) prompt calibration run | **2,000** questions (a *separate* set) |
| Activation-collection set (probing + steering-vector extraction) | **3,000** trials |
| Magistral behavioral run | 5,000 questions → **4,998** after filtering for valid answer + valid confidence class |
| Magistral activation set | **3,000** trials (stratified, see §12.4) |

- **Correctness labels:** TriviaQA free-text answers cannot be graded by string match reliably.
  The paper has **GPT-4o-mini mark each question** (model answer vs. gold aliases → correct /
  incorrect). Implement as a deterministic (temperature 0) single-call grader; feed the question,
  the gold answer aliases, and the model's answer, and require a bare `CORRECT`/`INCORRECT` token.
  Cache all grades to disk — you will reuse them across every experiment.

#### 2.3.2 Big-Math (generalization)

- **Source:** Big-Math (Albalak et al., 2025), `arXiv:2502.17387` — a large-scale RL-oriented math
  dataset with verifiable answers. Available on the Hugging Face hub.
- Used with **Gemma 3 27B + categorical prompt** only.
- Correctness is verifiable by answer matching (numeric/symbolic equality) rather than requiring
  the LLM grader.
- **Anchor:** Gemma scores **40.2% correct** on the subset used. If your accuracy is wildly
  different, you have selected a different difficulty stratum — Big-Math is stratified by
  difficulty, so match this accuracy by sampling accordingly.

#### 2.3.3 MMLU (generalization)

- **Source:** MMLU (Hendrycks et al., 2021), Hugging Face hub. **Multiple-choice** format.
- Used with **Gemma 3 27B + categorical prompt** only.
- Correctness is exact-match on the chosen option letter.
- **Anchor:** Gemma scores **76.8% correct**.
- Note that on MMLU the confidence distribution is heavily concentrated in high-confidence
  classes; this matters for trial-pool construction (§2.7) and produces asymmetric swap effects.

#### 2.3.4 Dataset disjointness requirements

Several sets must be **mutually disjoint**. Partition your deduplicated question pool *once*, up
front, and record the partition:

1. **Activation-collection set** — 3,000 trials. Used to (a) extract steering vectors, (b) train
   probes, (c) compute the natural pairwise activation-variability statistics for the OOD control.
2. **Calibration set** — 100 trials (50 high-confidence, 50 low-confidence). Used to compute the
   mean embeddings/activations for patching corruption and for noising. **Explicitly disjoint from
   the test set.**
3. **Test sets** — the per-experiment trial sets (200 for steering per layer/position, 200 for
   patching, 400 for noising, 400+400 for swap, 500 for attention blocking).

The paper states the steering test set uses "a separate set of questions as used in the main
activation steering experiment (n = 3000)" — i.e. steering vectors are extracted from the
3,000-trial activation set, and steering is *tested* on different questions.

### 2.4 The two-phase protocol

This is the backbone of the entire paper and must be implemented exactly.

**Phase 0 — answer generation.**
Present the model with a prompt "essentially identical" to the main confidence prompt **except
that the confidence instructions appear at the start** rather than after the answer. The model
generates its own answer. Record:

- the generated answer string,
- the per-token log-probabilities of every generated token (needed for §9's variance partitioning),
- the answer token span (map the extracted answer string back onto the generated token sequence),
- the Phase-0 verbal confidence report (used for the within-run vs cross-run consistency analysis).

The **last token of the Phase 0 prompt is the answer-colon (AC)** — the colon of `**Answer**:`,
whose final-layer residual stream is transformed by the unembedding matrix to produce the logits
over the *first answer token*. AC is the key control position for Experiment 7.

**Phase 1 — confidence elicitation.**
Re-present the question **with the model's own Phase-0 answer already inserted into the prompt**
(see the prompt templates in §2.5), and ask for a confidence rating.

**Why inserting the answer is legitimate and not a confound.** A transformer's forward pass is a
pure function of the preceding tokens. Placing the previously generated answer into the context
yields *the exact same residual-stream representation at PANL* as autoregressive generation would
have. This is what makes it possible to run single, cacheable, intervention-friendly forward
passes instead of sampling.

**Consequence for reproduction:** you must insert the model's *own* Phase-0 answer verbatim —
never the gold answer, never a re-sampled answer.

### 2.5 Prompts (verbatim)

Reproduce these character-for-character. Tokenization of the target positions depends on it.

#### 2.5.1 Main categorical confidence prompt (Gemma 3 27B, Qwen 2.5 7B) — "Figure 8"

```
"""You will be shown a question, together with an answer you previously provided before.

Question: {question}
**Answer**: {answer}
                        <-- (1) post_answer_newline token  [PANL]
Classify your confidence into one of the following classes based on how
likely the answer above is to be correct (NO REASONING OR EXPLANATION):

- "No chance" (0.0–0.1)
- "Really unlikely" (0.1–0.2)
- "Chances are slight" (0.2–0.3)
- "Unlikely" (0.3–0.4)
- "Less than even" (0.4–0.5)
- "Better than even" (0.5–0.6)
- "Likely" (0.6–0.7)
- "Very good chance" (0.7–0.8)
- "Highly likely" (0.8–0.9)
- "Almost certain" (0.9–1.0)

Each category reflects the probability that the answer is correct.

At the very end of your output, format your confidence as
**Confidence**: $CLASS
where CLASS is one of the names (only the names without the probability ranges)
of the classes above.

**Confidence**:"""
                ^-- (2) confidence_colon token  [CC]
```

Written out literally (the arrow annotations above are figure labels, not prompt text), the
template is:

```text
You will be shown a question, together with an answer you previously provided before.

Question: {question}
**Answer**: {answer}
Classify your confidence into one of the following classes based on how
likely the answer above is to be correct (NO REASONING OR EXPLANATION):

- "No chance" (0.0–0.1)
- "Really unlikely" (0.1–0.2)
- "Chances are slight" (0.2–0.3)
- "Unlikely" (0.3–0.4)
- "Less than even" (0.4–0.5)
- "Better than even" (0.5–0.6)
- "Likely" (0.6–0.7)
- "Very good chance" (0.7–0.8)
- "Highly likely" (0.8–0.9)
- "Almost certain" (0.9–1.0)

Each category reflects the probability that the answer is correct.

At the very end of your output, format your confidence as
**Confidence**: $CLASS
where CLASS is one of the names (only the names without the probability ranges)
of the classes above.

**Confidence**:
```

**The single most important design property.** This prompt is derived from Yoon et al. (2025) but
**modified so that the first token of every confidence class is unique.** Verify this with your
tokenizer before running anything:

```python
CLASSES = ["No chance", "Really unlikely", "Chances are slight", "Unlikely",
           "Less than even", "Better than even", "Likely", "Very good chance",
           "Highly likely", "Almost certain"]
first_ids = [tok(" " + c, add_special_tokens=False).input_ids[0] for c in CLASSES]
assert len(set(first_ids)) == 10, "class-initial tokens collide — metrics 2 and 3 are invalid"
```

If two classes shared a first token, the *first-token change rate* and *logit difference* metrics
would be meaningless. (Note the leading-space convention: the class name follows `**Confidence**:`,
so the realized first token is the space-prefixed variant. Determine empirically which variant the
model actually emits and use that consistently.)

**Class → confidence midpoint mapping** (used everywhere as the numeric confidence value):

| Class | Range | **Midpoint** |
|---|---|---|
| No chance | 0.0–0.1 | **0.05** |
| Really unlikely | 0.1–0.2 | **0.15** |
| Chances are slight | 0.2–0.3 | **0.25** |
| Unlikely | 0.3–0.4 | **0.35** |
| Less than even | 0.4–0.5 | **0.45** |
| Better than even | 0.5–0.6 | **0.55** |
| Likely | 0.6–0.7 | **0.65** |
| Very good chance | 0.7–0.8 | **0.75** |
| Highly likely | 0.8–0.9 | **0.85** |
| Almost certain | 0.9–1.0 | **0.95** |

**High-confidence band** = top three classes = {Highly likely, Very good chance, Almost certain}.
**Low-confidence band** = bottom three classes = {No chance, Really unlikely, Chances are slight}.
These two bands are used for every H/L trial split in the paper.

#### 2.5.2 Full numeric confidence prompt (Gemma 3 27B) — "Figure 15"

Derived from Mei et al. (2025) and Devic et al. (2025).

```text
You will be shown a question, together with an answer
you previously provided before.
Question: {question}
**Answer**: {answer}

State your confidence as an integer between 0 and 100 based
on how likely your answer is to be correct.
That is, if your confidence is 0, that means that your
answer has almost no chance of being correct.
If your confidence is 100, then you are almost certain that your
answer is correct.

At the very end of your output, format your confidence as:
**Confidence**:$CONFIDENCE
where CONFIDENCE is an integer between 0 and 100.
do NOT leave a space before the first digit or you will be
scored WRONG!
**Confidence**:
```

Note the deliberate instruction to omit the space before the first digit — this makes the first
generated token a bare digit, keeping the first-token metrics well-defined.

#### 2.5.3 Minimal numeric confidence prompt (attention blocking only) — "Figure 16"

Elicits confidence on a **0–9** scale as a **single token**, and — crucially — minimizes the number
of intermediate template tokens between PANL and CC, so that a direct CC→PANL attention edge can
actually be tested. In the full categorical prompt there are **more than a hundred** intermediate
tokens, which provide redundant multi-hop routing that masks the direct pathway.

```text
You will be shown a question, together with an
answer you previously provided before.
Question: {question}
**Answer**: {answer}
                        <-- (1) post_answer_newline token  [PANL]
**State Confidence(0-9) with NO SPACE**:'
                                        ^-- (2) confidence_colon token  [CC]
```

Literal template:

```text
You will be shown a question, together with an
answer you previously provided before.
Question: {question}
**Answer**: {answer}
**State Confidence(0-9) with NO SPACE**:'
```

(The trailing apostrophe is present in the paper's figure and is part of the prompt.)

#### 2.5.4 Magistral Phase 1 prompt (CoT answer generation) — "Figure 24"

```text
Answer the following question. Think step by step and give your final answer.
Question: {question}
After your reasoning, state your final answer as:
**Answer**: $ANSWER
where ANSWER is your final answer stated as concisely as possible.
```

`max_new_tokens = 1024`, greedy.

#### 2.5.5 Magistral Phase 2 prompt (confidence elicitation with trace) — "Figure 23"

The model's **full reasoning trace followed by its extracted final answer** is presented back
inside a response block, then the categorical confidence instructions follow.

```text
You will be shown a question, together with a response you previously provided
before.
Question: {question}
**Your response**: {full_reasoning_trace}
**Answer**: {extracted_answer}
Classify your confidence into one of the following classes based on how likely
the answer above is to be correct (NO REASONING OR EXPLANATION):

- "No chance" (0.0–0.1)
- "Really unlikely" (0.1–0.2)
- "Chances are slight" (0.2–0.3)
- "Unlikely" (0.3–0.4)
- "Less than even" (0.4–0.5)
- "Better than even" (0.5–0.6)
- "Likely" (0.6–0.7)
- "Very good chance" (0.7–0.8)
- "Highly likely" (0.8–0.9)
- "Almost certain" (0.9–1.0)

Each category reflects the probability that the answer is correct.
At the very end of your output, format your confidence as
**Confidence**: $CLASS
where CLASS is one of the names (only the names without the probability ranges)
of the classes above.
**Confidence**:
```

For Magistral, **PANL is defined as the newline token terminating the response block** (i.e. the
newline after the extracted answer, immediately before `Classify your confidence...`), and
**PANL+1** is the token right after it. CC is, as always, the very last token of the prompt.

#### 2.5.6 Chain-of-thought suppression (main experiments)

The main experiments **deliberately suppress chain-of-thought** at the confidence stage — hence
`(NO REASONING OR EXPLANATION)` in the prompt. This is intentional and load-bearing:

- It is practically relevant (auto-rating/grading deployments skip CoT to cut cost).
- It makes confidence a single-token readout, enabling the whole layer × position sweep.
- Even in reasoning models, decisions like backtracking must be driven by latent signals inside
  the forward pass, not by externalized tokens — so the no-CoT setting is not a toy case.

Do not "helpfully" allow the model to reason at the confidence stage; it breaks the single-forward-
pass design and changes the position semantics.

### 2.6 Token positions — the central objects of study

Every experiment is defined over these positions. Locate them by tokenizing the prompt once per
trial and recording indices; do not hard-code offsets, since question and answer lengths vary.

| Abbrev. | Name | Definition | Role |
|---|---|---|---|
| **AC** | answer-colon | Last token of the **Phase 0** prompt (the colon of `**Answer**:`); its final-layer residual stream produces the first answer token's logits | Test of the first-order account |
| **first A** | first answer token | First token of the model's answer | Probe |
| **last A** | last answer token | Final token of the model's answer | Effective for steering, but **confounded** (it is itself answer content), so excluded from the main analyses |
| **PANL** | post-answer newline | The `\n` immediately following `**Answer**: {answer}` | **Primary hypothesised cache site** |
| **PANL+1** | — | The token immediately after PANL | **Primary control** |
| **FCC** | first-confidence-colon | The colon preceding `$CLASS` in the instruction block (`**Confidence**: $CLASS`) | Secondary control (steering) |
| **CC** | confidence-colon | The **very last token of the prompt** — the final `**Confidence**:` colon | **Verbalization site** |
| **QTT** | third question token | Third token of the question | Control for probing |
| **Trace k%** | reasoning-trace positions | Magistral only: tokens sampled at 10% increments across the CoT trace | Probing in the CoT regime |

**Why `last A` is dropped from the main analyses.** Steering at the last answer token *is*
effective — consistent with confidence-relevant information being available once the full question
and most of the answer have been encoded. But the last answer token is *itself part of the answer
content*, so it conflates two roles: a potential cache of confidence, and the semantic content
(answer correctness) from which confidence is presumably derived. PANL has no such confound: it
immediately follows the answer and carries no answer content of its own. Steering at the **first**
answer token is ineffective.

**Implementation note.** Confirm the newline after the answer is a *single* token in your
tokenizer and is not merged with adjacent characters. For Gemma/Qwen/Mistral tokenizers, check
explicitly — if `\n` merges with the following word, PANL is not isolable and the entire
experiment's position semantics break.

### 2.7 Trial pools and how to build them

The models are **biased toward high confidence** (see §3), so naive sampling gives you almost no
low-confidence trials. Every experiment therefore uses an explicitly balanced or extreme-sampled
pool.

**Gemma / Qwen, categorical prompt:**

- **High-confidence trials**: model's clean report ∈ {Highly likely, Very good chance, Almost certain}.
- **Low-confidence trials**: model's clean report ∈ {No chance, Really unlikely, Chances are slight}.
- **Steering test trials**: 200 per layer per position, **half sampled from the top-3 classes,
  half from the bottom-3 classes**, to ensure balance.
- **Steering vector extraction**: the **25 highest-ranked** ("Almost certain") and **25
  lowest-ranked** ("No chance") trials, restricted to trials the model **answered correctly**.
- **Patching**: 200 high-confidence trials (top-3 classes), selected on the basis of the original
  Phase 0 report.
- **Noising**: 400 trials per layer per position; calibration set 100 (50 high + 50 low).
- **Swap**: 400 high-confidence recipients and 400 low-confidence recipients. The low pool has
  only **N = 221 available**, so it is **sampled with replacement** to reach 400.

**Qwen-specific adjustment.** Qwen's confidence distribution is narrower, so the H/L contrast is
taken from adjacent-but-separated classes: **low = "Unlikely"**, **high = "Likely"**.

**Magistral-specific adjustment.** 92% of Magistral's reports are "Almost certain". Trials are
therefore drawn from the **extremes of the confidence distribution sorted by midpoint**, rather
than uniformly within a band. The activation set is stratified: retain **all** trials with verbal
confidence ≤ 0.7, then fill the remainder by random sampling from high-confidence trials, to
preserve the scarce low-confidence pool needed for H/L contrasts.

### 2.8 Metrics

Three metrics recur throughout. Implement them once.

Let `z ∈ R^V` be the next-token logits at the final prompt position. Let `K = 10` be the number of
confidence classes (or, for the numeric prompts, the 10 digits 0–9), and let `y` be the class the
**clean** (unintervened) run predicted.

#### (1) Logit difference

$$\Delta_{\text{logit}} = z_y - \frac{1}{K-1}\sum_{k \neq y} z_k$$

The logit of the clean trial's confidence class minus the **mean logit of the 9 alternative
classes**. Computed over the class-initial token IDs only, not the full vocabulary.

*Why logits and not probabilities:* the model's computations are linear in logit space right up
until the final softmax, so logit differences are the interpretable quantity for a linear
intervention. This follows Wang et al. (2023) / Heimersheim & Nanda (2024) / Rai et al. (2024).

**Logit difference change** = (intervened Δ_logit) − (clean Δ_logit). Always report the *change*,
keeping the target class `y` fixed at the clean prediction.

#### (2) Confidence (and confidence change)

Confidence = **the midpoint of the predicted class's probability range** (table in §2.5.1).
E.g. "Highly likely" (0.8–0.9) → 0.85.

**Confidence change** = intervened confidence − clean confidence.

For the **full numeric prompt**, confidence is simply the generated integer 0–100, and confidence
change is the integer difference.

#### (3) First token change rate

$$\text{Change Rate} = \frac{1}{N}\sum_{i=1}^{N} \mathbb{1}\!\left[\arg\max_k z_k^{(\text{patched},i)} \neq \arg\max_k z_k^{(\text{clean},i)}\right]$$

The proportion of trials on which the argmax confidence token differs from the clean baseline.
For the numeric prompts this becomes the **first digit change rate**.

#### (4) Percent recovery (patching only)

For a metric `M`:

$$\text{Recovery}_M = \frac{M_{\text{patched}} - M_{\text{corrupt}}}{M_{\text{clean}} - M_{\text{corrupt}}} \times 100\%$$

100% = complete restoration of clean behavior; 0% = no improvement over the corrupted baseline.

For **first token change rate**, where *lower* means better recovery (the clean baseline has 0%
change), invert:

$$\text{Recovery}_{\text{token}} = \frac{\text{Rate}_{\text{corrupt}} - \text{Rate}_{\text{patched}}}{\text{Rate}_{\text{corrupt}}} \times 100\%$$

#### (5) Calibration metrics

- **ECE (Expected Calibration Error)**: standard binned calibration error between stated
  confidence and empirical accuracy. Use 10 bins (matching the 10 confidence classes for the
  categorical prompt; 10 equal-width bins for numeric).
  **No temperature scaling** (Guo et al., 2017) or any other post-hoc recalibration is applied —
  the point is to study the model's *raw* verbal confidence signal.
- **AUROC**: area under the ROC curve for discriminating correct from incorrect answers using the
  stated confidence as the score.

#### (6) Error bars

All plots show **SEM** across trials. Report SEM, and treat a condition as "showing an effect"
only when it separates from the PANL+1 control by clearly non-overlapping SEM bars.

### 2.9 Layer sweep

**Gemma 3 27B (62 layers).** Sweep layers:

```
0, 10, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 40, 50, 61
```

That is: coarse sampling early and late, **dense (every-layer) sampling across layers 20–35**,
where all the effects live. Use this exact set so your x-axis matches the paper's figures.

**Qwen 2.5 7B (28 layers).** Dense sweep across **all** layers 0–27.

**Magistral (40 layers).** Dense sweep across all 40 layers (the paper reports layerwise probing
across all 40).

**Attention blocking** uses a different sweep convention — see §11.

### 2.10 Reference hook infrastructure

All four activation interventions (steer / patch / noise / swap) are the same operation: replace
or modify the residual stream at **one token position** at **one layer**. Build one hook utility.

**Where in the block to intervene.** The paper specifies for patching that the intervention is
**applied after the MLP block at each layer** — i.e. on the residual stream *output* of the
decoder layer. Apply all residual-stream interventions at that same point for consistency.

```python
import torch
from contextlib import contextmanager

def _layers(model):
    # Gemma3 / Qwen2 / Mistral all expose the decoder stack here:
    return model.model.layers

@contextmanager
def residual_intervention(model, layer_idx, fn):
    """fn(hidden_states) -> hidden_states, applied to the output of decoder layer `layer_idx`
    (i.e. after that layer's MLP block, on the residual stream)."""
    def hook(module, args, output):
        # HF decoder layers return a tuple whose first element is the hidden states
        if isinstance(output, tuple):
            return (fn(output[0]),) + output[1:]
        return fn(output)
    h = _layers(model)[layer_idx].register_forward_hook(hook)
    try:
        yield
    finally:
        h.remove()

# --- the four interventions, all as `fn` factories -------------------------

def steer(pos, vec, alpha):
    def fn(hs):                      # hs: (batch, seq, d_model)
        hs = hs.clone()
        hs[:, pos, :] = hs[:, pos, :] + alpha * vec.to(hs.dtype).to(hs.device)
        return hs
    return fn

def replace(pos, new_vec):           # used for noising (mean) and swap (donor)
    def fn(hs):
        hs = hs.clone()
        hs[:, pos, :] = new_vec.to(hs.dtype).to(hs.device)
        return hs
    return fn

def patch(pos, clean_vec):           # identical mechanics to `replace`; semantics differ
    return replace(pos, clean_vec)
```

**Caching clean activations.** For patching and swapping you need the *clean* residual stream at
every (layer, position) of interest. Capture with a forward hook on the same points during an
un-intervened pass and store to CPU (float16) — 3,000 trials × 22 layers × ~7 positions ×
5,376 dims is a few GB, which is manageable; store per-position files.

**Embedding-level corruption** (patching only) is different — it operates on the *input
embeddings*, before layer 0, so that corruption propagates through the whole forward pass. Use
`inputs_embeds=` rather than `input_ids=`:

```python
emb = model.get_input_embeddings()(input_ids)         # (1, seq, d)
emb[:, answer_positions, :] = mean_answer_embeddings   # corruption
out = model(inputs_embeds=emb, attention_mask=mask)
```

---

## 3. Experiment 0 — Behavioral baseline and calibration

**Purpose.** Establish that the model produces a meaningful, reasonably calibrated confidence
signal at all, and generate the Phase-0/Phase-1 records that every later experiment consumes.
This is a prerequisite, not an optional preliminary — if calibration is far off, your prompt or
answer-extraction is wrong and no downstream result will replicate.

### 3.1 Procedure

1. Load `google/gemma-3-27b-it`, bf16, eval mode, greedy.
2. Load and deduplicate TriviaQA; draw 7,858 questions for the categorical run.
3. **Phase 0:** For each question, run the Phase-0 prompt (main prompt with confidence
   instructions moved to the start). Greedily generate. Record:
   - answer string (parse out of `**Answer**: ...`),
   - per-token log-probabilities `log p(t_i | t_<i, x)` for the generated sequence,
   - the answer token span (map the extracted answer string back to token indices),
   - the Phase-0 confidence class.
4. **Phase 1:** For each question, build the main categorical prompt (§2.5.1) with the model's own
   Phase-0 answer inserted. Run **one forward pass**. Take the argmax over the ten class-initial
   token IDs at the final position → the confidence class. Record the full logit vector over those
   ten IDs.
5. **Grade** all answers with GPT-4o-mini → binary correctness.
6. Compute accuracy, ECE (10 bins, no temperature scaling), AUROC (confidence vs correctness),
   and the histogram of classes.
7. Repeat for the **numeric prompt** (n = 8,008; `max_new_tokens=4`), the **minimal numeric
   prompt** (a separate n = 2,000), and for Qwen / BigMath / MMLU / Magistral as needed.

### 3.2 Auxiliary check — rule out hedging

A confounding worry for the steering experiment is that "confidence directions" might actually
encode *linguistic hedging* ("maybe", "probably", "perhaps") rather than confidence per se. The
paper rules this out by **having GPT-4o-mini verify that none of the answers in the dataset
contain hedging language.** TriviaQA answers are typically only a few tokens long, so this is
easy to satisfy — but run the check and report the result.

Implementation: batch the answer strings to GPT-4o-mini with a yes/no classification prompt
("Does this answer contain hedging language such as 'maybe', 'probably', 'perhaps'?"), temperature
0, and confirm a ~0% hedging rate. If your pipeline produces long, hedged answers, your Phase-0
prompt is wrong.

### 3.3 Expected results (validation targets)

| Model / prompt | n | Accuracy | **ECE** | **AUROC** | Distribution |
|---|---|---|---|---|---|
| Gemma 3 27B, categorical, TriviaQA | 7,858 | **77.4%** | **0.12** | **0.71** | Uses both ends of the 10-class spectrum with reasonable frequency, **weighted toward high confidence** |
| Gemma 3 27B, numeric 0–100, TriviaQA | 8,008 | — | **0.16** | **0.73** | 10 bins, skewed high |
| Gemma 3 27B, minimal numeric 0–9, TriviaQA | 2,000 | — | **0.17** | **0.68** | — |
| Qwen 2.5 7B, categorical, TriviaQA | (same subset) | — | **0.06** | **0.65** | Narrower spread; H/L contrast taken from "Likely" vs "Unlikely" |
| Gemma 3 27B, categorical, BigMath | — | **40.2%** | — | — | — |
| Gemma 3 27B, categorical, MMLU | — | **76.8%** | — | — | Overwhelmingly high-confidence |
| Magistral Small 24B, categorical, TriviaQA | 4,998 | — | "reasonably well calibrated" | — | **92% "Almost certain"** |

**Interpretation.** Gemma is reasonably calibrated (ECE 0.12) and its verbal confidence
discriminates correct from incorrect at AUROC 0.71 — a meaningful signal, which is the
precondition for the mechanistic analysis to be about anything. Note for later: the
length-normalized mean answer log-probability achieves **AUROC 0.75** for correctness, i.e.
*better* than the verbal report — this is the well-known calibration gap between white-box and
verbalized confidence, and it is exactly why the second-order question in §9 is non-trivial.

**Baseline confidence values** (mean confidence of the trial sets used in the intervention
experiments) — you will need these as the zero-point for confidence-change plots:

| Setting | Baseline confidence |
|---|---|
| Gemma categorical, steering trial set (main text, n=200) | **0.55** |
| Gemma categorical, steering (Figure 22 summary set) | **0.48** |
| Gemma numeric prompt | **0.54** |
| Qwen categorical | **0.56** |

(The two Gemma categorical values differ because they are different trial subsets; both are
reported in the paper.)

---

## 4. Experiment 1 — Activation steering

> **Question:** *Where* — at which token positions and which layers — is confidence represented?
> **Key result:** Confidence is modulated at PANL (layers 21–25), then at CC (layers 30–35);
> control positions show no effect.

### 4.1 Logic

If verbal confidence reflects access to a meaningful internal uncertainty signal, that signal must
be instantiated as a direction in activation space. Prior work shows transformers encode abstract
properties (e.g. love/hate) as linear directions (Turner et al., 2023), so high- and low-confidence
trials should differ along an identifiable direction. Extracting that direction at each
(layer, position) and injecting it lets you map where confidence-relevant information *lives*.

**Discriminating prediction.** Under JIT, no confidence-specific computation exists until CC, so
steering at PANL should be **ineffective** — PANL may carry answer-related information, but not a
dedicated, directly modulable confidence representation. (Causal attention means PANL cannot know
a rating will be requested.) Under cached retrieval, steering at PANL **should** work, and PANL
effects should emerge at **earlier layers** than CC effects.

Both accounts predict steering at CC works, so **CC alone is not diagnostic** — PANL is.

### 4.2 Building the steering vectors

From the **3,000-trial activation-collection set** (separate from the steering test questions),
restricted to **trials the model answered correctly**:

- `H` = the **25 highest-ranked** trials by confidence, i.e. class "Almost certain".
- `L` = the **25 lowest-ranked** trials, i.e. class "No chance".

For each layer ℓ and position p:

$$v_{\text{high}}^{(\ell,p)} = \mu(H)^{(\ell,p)} - \mu(L)^{(\ell,p)}, \qquad v_{\text{low}}^{(\ell,p)} = -\,v_{\text{high}}^{(\ell,p)}$$

where μ(·) is the mean residual-stream activation across the selected trials. The low-confidence
vector is exactly the negation of the high-confidence vector.

**Normalization (critical).** Scale each steering vector to **3% of the residual norm at that
layer**, then multiply by a strength constant α:

```python
v = v / v.norm()
v = v * 0.03 * mean_residual_norm_at_layer          # 3% of residual norm
h_steered = h + alpha * v                           # alpha ∈ {2, 5}  (also 1, 10 in Fig 29)
```

`mean_residual_norm_at_layer` = the mean L2 norm of the residual stream at that layer (average
over the activation-collection trials at the position being steered).

Steering strengths **α ∈ {2, 5}** for the main figures (solid = 2, dotted = 5); the paper also
shows α ∈ {1, 10} produce effects. These values were chosen empirically and — verified in
Experiment 5 — do **not** push the model out of distribution.

### 4.3 Application at test time

$$\tilde{r}^{(\ell)} = r^{(\ell)} + \alpha\, v^{(\ell)}$$

applied at a **single position, single layer** — additively, on the residual stream, at the output
of the decoder layer. Then read the next-token logits and compute the metrics.

### 4.4 Trial counts and conditions

- **200 questions per layer per position.**
- Balanced: **half randomly sampled from the top-3 confidence classes, half from the bottom-3**
  (necessary because the model favors high-confidence classes).
- **Positions:** PANL, CC (key); PANL+1, FCC (controls); plus first answer token and last answer
  token (reported separately); plus AC (Experiment 7).
- **Directions:** high-confidence steering and low-confidence steering.
- **Layers:** the sweep in §2.9.

Full grid for the main figure: 4 positions × 2 directions × 2 scales × 22 layers × 200 trials.

### 4.5 Analysis

Plot **Δ confidence** (steered midpoint − clean midpoint) against layer, one panel per position,
with separate lines for high/low steering × scale 2/5, error bars = SEM.

### 4.6 Expected results

| Position | Effect | Peak layers | Magnitude (Δ confidence, α=5) |
|---|---|---|---|
| **PANL** | **Strong, bidirectional, graded** | **21–25** | high ≈ **+0.15 to +0.20**; low ≈ **−0.20** |
| **CC** | **Strong, bidirectional** | **30–35** (extending to ~40–61) | high ≈ **+0.40**; low ≈ **−0.40** |
| PANL+1 | **Null** | — | ≈ ±0.02 (noise) |
| FCC | **Null** | — | ≈ ±0.02 (noise) |
| First answer token | **Null** | — | — |
| Last answer token | Effective (but confounded; excluded from later analyses) | — | — |
| **AC (answer-colon)** | **Null** — indistinguishable from PANL+1 | — | — |

Baseline confidence across trials: **0.55**.

**How to interpret / validate.**
1. The **existence** of a PANL effect falsifies JIT. This is the headline.
2. The **temporal ordering** — PANL peaks at 21–25, CC at 30–35 — is the signature of cached
   retrieval: information is consolidated at PANL, then transferred to CC for verbalization. If
   you get PANL and CC peaking at the same layers, something is wrong with your position indexing.
3. **The controls must be null.** PANL+1 sits one token away from PANL; if it shows effects, your
   intervention is leaking (e.g. you are steering a slice rather than a single position, or your
   vector is so large it disrupts the model generically — check §8).
4. The AC null result, together with §9's variance partitioning, is what rules out the first-order
   account.

**Cross-model peak layers** (from the summary figure):

| Model / prompt | PANL peak | PANL+1 peak | CC peak |
|---|---|---|---|
| Gemma categorical | L25 | L28 | L30 |
| Gemma numeric | L25 | L31 | L31 |
| Qwen categorical | L15 | L1 | L22 |

Note Qwen (28 layers) shows the same *relative* ordering at proportionally scaled depths.

---

## 5. Experiment 2 — Activation patching (corrupt-then-restore)

> **Question:** Are PANL activations **sufficient** to drive verbal confidence reporting?
> **Key result:** Restoring PANL partially recovers confidence after answer corruption; PANL's
> recovery peaks earlier (L25) than CC's (which rises only after L30).

### 5.1 Logic

Destroy the model's access to answer information, then selectively restore a *single* position at
a *single* layer. If that position at that layer contains sufficient information to drive
confidence output, restoring it should recover the model's original confidence behavior despite
corruption still propagating everywhere else.

### 5.2 Step 1 — Corruption of answer tokens via mean ablation

Let `x_i^(0)` be the input embedding of token `i`, and `A = {a_1, ..., a_k}` the set of **answer
token positions**. From a **calibration set C of 100 trials (50 high-confidence, 50 low-confidence,
disjoint from the test set)**, compute the mean embedding at each answer position `j`:

$$\bar{x}_j^{(0)} = \frac{1}{|C|}\sum_{c \in C} x_{j,c}^{(0)}$$

For each test trial, **replace all answer token embeddings with these means**. The corruption is
applied **at the input embedding level**, so it propagates through the entire forward pass and
effectively prevents the model from assessing whether its answer was correct.

Practical detail: answer spans have different lengths across trials. Compute the mean *per answer
position index j* (1st answer token, 2nd answer token, …) across calibration trials that have at
least that many answer tokens.

### 5.3 Step 2 — Patching

Let `h_p^(ℓ)` be the residual stream at position `p` after layer `ℓ`. Let `h_p^(ℓ,clean)` be the
activation from a clean forward pass (no corruption) and `h_p^(ℓ,corrupt)` the activation with
answer tokens mean-ablated. The intervention restores the clean value at exactly one
(position, layer):

$$h_p^{(\ell,\text{patched})} \leftarrow h_p^{(\ell,\text{clean})}$$

while **all other positions retain their corrupted activations.** Applied **after the MLP block**
at that layer.

### 5.4 Conditions

- **Positions:** PANL, CC, **PANL+1 (control)**.
- **Layers:** the §2.9 sweep.
- **Trials:** **200 high-confidence trials** (top-3 classes), selected on the basis of the original
  Phase 0 report.
- **Why only high-confidence trials:** they provide the clearest test. Corruption should
  substantially *reduce* confidence; low-confidence trials are already near floor and thus
  insensitive to disruption.

### 5.5 Baselines to compute first

- **Clean baseline**: no corruption, no patching.
- **Corrupt baseline**: corruption, no patching.

### 5.6 Metrics

All three (§2.8), plus **percent recovery** for each.

### 5.7 Expected results

**Corrupt baseline (validation gate — get this before anything else):**

- Model's confidence **decreases to the lowest class**.
- Logit difference **collapses to near zero** (clean ≈ **11.5**, corrupt ≈ **0**).
- **100% first-token change rate.**

If corruption does not do this, your answer-span mapping is wrong.

**Patching results:**

| Position | Logit-diff recovery | Confidence recovery | Token-change recovery | Peak layer |
|---|---|---|---|---|
| **PANL** | **Partial** (Δlogit rises to ≈ **2.3** of ≈11.5; ~20% recovery) | **Partial** (confidence rises to ≈ **0.40**; ~24% recovery at L25) | Change rate drops from 100% to ≈ **78%** | **L25** |
| **CC** | **Near-complete** (rises to ≈ **12** by L61) | **Near-complete** (≈ **0.85**) | Change rate drops to ≈ **5%** | **rises sharply only after L30**, peaking L40–61 |
| **PANL+1** | **≈ 0** | **≈ 0** (−1.4% recovery) | ≈ 0 | none |

**How to interpret / validate.**

1. **Near-ceiling CC recovery at late layers is expected and is NOT the interesting result.** CC's
   residual stream is directly transformed by the unembedding matrix at the final layer, so
   patching it late simply bypasses all upstream corruption. Do not over-read it.
2. **The informative result is the layer-wise pattern**: PANL peaks at **L25**; CC rises only
   after **L30**. This temporal precedence is the cached-retrieval signature.
3. **Partial PANL recovery is expected, not a failure.** Two reasons the paper gives:
   (a) the intervention restores a *single position at a single layer* while corruption continues
   to propagate through all other positions and layers — full recovery would require patching the
   complete distributed circuit; (b) model behaviors typically arise from many overlapping
   heuristics rather than one clean circuit (unlike, say, the indirect-object-identification
   circuit), so cached retrieval is plausibly one of several overlapping mechanisms. The paper
   explicitly positions cached retrieval as the **dominant** rather than the **sole** pathway.
4. **PANL+1 must be flat at zero.** This is the whole force of the result: a position one token
   away, with near-identical out-of-distribution drift (§8), does nothing.

**Cross-model peak layers:** Gemma categorical PANL L25 / PANL+1 L0 / CC L61; Gemma numeric PANL
L25 / PANL+1 L0 / CC L40; Qwen PANL L15 / PANL+1 L27 / CC L27.

---

## 6. Experiment 3 — Activation noising (mean ablation)

> **Question:** Are PANL and CC representations **necessary** for confidence reporting?
> **Key result:** Ablating PANL partially disrupts confidence (peak L25–26); CC disrupts from L30
> onward; PANL+1 does nothing.

### 6.1 Procedure

For each position of interest, **replace its residual-stream activation with the mean activation**
computed from a **balanced calibration set of 100 trials**:

- 50 high-confidence trials from the top three classes ("Highly likely", "Very good chance",
  "Almost certain"), and
- 50 low-confidence trials from the bottom three classes ("No chance", "Really unlikely",
  "Chances are slight").

This calibration set is **disjoint from the test set**.

Apply at a **single layer at a time**, at a **single position**, across the §2.9 layer sweep.

- **Positions:** PANL, CC, **PANL+1 (control)**.
- **Trials:** **n = 400 per layer per position.** (Unlike patching, this uses *all* trials, not
  just high-confidence ones.)

### 6.2 Important conceptual note (do not mis-implement)

Mean ablation does **not** push the model toward a semantically meaningful "neutral" confidence
state. The mean of activations encoding high and low confidence is **not** an encoding of medium
confidence — analogously, averaging the word embeddings of "brilliant" and "terrible" does not
give you "mediocre". Mean ablation instead **disrupts** the position's contribution by replacing
trial-specific information with an uninformative average. So interpret the result as *disruption*,
not as *setting confidence to 0.5*.

### 6.3 Metrics

The paper focuses on the **two metrics that best capture disruption**:

1. **Logit difference change** (clean vs noised), and
2. **First token change rate**.

Confidence change is not the primary readout here (for the reason in §6.2).

**Directional prediction:** if a position is necessary, ablating it should **reduce logit
difference** and **increase first-token change rate**. If ablation has no effect, the position is
not necessary for the confidence-reporting mechanism.

### 6.4 Expected results

Clean logit difference ≈ **9.4**.

| Position | Logit diff after noising | First-token change rate | Peak layer |
|---|---|---|---|
| **PANL** | dips to ≈ **8.4** (a ~1.0-point / ~11% reduction) | peaks ≈ **14%** | **L25–26** |
| **CC** | falls steeply to ≈ **2.8** by L61 | rises to ≈ **78%** | **rises after L30**, max at L61 |
| **PANL+1** | **flat at clean (≈9.4)** | **flat ≈ 3–4%** | none |

**How to interpret / validate.**

- PANL and CC ablation causes **partial** disruption; PANL+1 causes none. This establishes
  necessity (partial) for PANL and CC.
- **The same temporal precedence appears again**: PANL peaks at L25–26, CC only after L30.
- The **partial** rather than complete disruption is expected, reflecting either (a) confidence
  encoding distributed across layers, so ablating one layer leaves other layers' contributions
  intact, or (b) functional redundancy — alternative pathways partially compensating.
- The CC effect at very late layers is again partly trivial (CC feeds the unembedding directly);
  the diagnostic content is the PANL effect and its earlier peak.

**Cross-model peak layers:** Gemma categorical PANL L25 / PANL+1 L15 / CC L61; Gemma numeric PANL
L26 / PANL+1 L26 / CC L61; Qwen PANL L11 / PANL+1 L6 / CC L21.

---

## 7. Experiment 4 — Activation swap (interchange intervention)

> **Question:** Does PANL carry **confidence-specific** information, or merely answer *content*
> that happens to correlate with confidence?
> **Key result:** Cross-confidence swaps shift confidence **directionally** across unrelated Q–A
> pairs, beyond same-confidence controls. Peak L26.

### 7.1 Logic

This is the decisive disambiguation, and follows the logic of interchange intervention (Geiger et
al., 2021). Transplant the PANL residual-stream activation from a **donor** trial into a
**recipient** trial, leaving the recipient's question and answer completely unchanged.

- If PANL caches a **confidence representation**, a cross-confidence swap (e.g. low-confidence
  donor → high-confidence recipient) should **systematically bias the recipient toward the donor's
  confidence level**, directionally.
- If PANL primarily encodes **content-specific features**, cross-confidence swaps should produce
  only generic disruption that does **not depend on the donor's confidence** and is of similar
  magnitude to same-confidence control swaps.

### 7.2 Design — 2 × 2 factorial

Crossing **recipient confidence** (high/low) × **donor confidence** (high/low):

| Condition | Meaning | Role |
|---|---|---|
| **H→H** | high recipient receives high donor | **Control** (same-confidence) |
| **L→L** | low recipient receives low donor | **Control** (same-confidence) |
| **H→L** | high recipient receives **low** donor | **Cross-confidence** — should *decrease* confidence |
| **L→H** | low recipient receives **high** donor | **Cross-confidence** — should *increase* confidence |

The same-confidence conditions control for generic cross-trial substitution effects: *any* swap
introduces a foreign internal state that may disrupt processing independently of confidence.
Comparing cross- to same-confidence swaps **on the same recipient trials** isolates effects
attributable specifically to the donor's confidence level.

### 7.3 Recipient and donor construction

- **Fix the recipient set within each regime.** The **same 400 high-confidence recipients** are
  used in both H→H and H→L; the **same 400 low-confidence recipients** in both L→L and L→H. This
  is essential — it makes the control a within-trial comparison.
- Partition trials by the model's **clean** confidence report:
  - high = {Highly likely, Very good chance, Almost certain} — N > 400 available;
  - low = {No chance, Really unlikely, Chances are slight} — **N = 221 available**, so **sample
    with replacement** to reach 400.

**Donor–recipient length matching (required).** To control for prompt-length effects on attention
patterns and decoding dynamics, **match donors to recipients on tokenized question length and
answer length using quantile bins.**

Reported matching quality, which you should reproduce and report:

- question-length bins matched in **100%** of cases;
- answer-length bins matched in **94–100%** of cases;
- mean |ΔL_Q| ≈ **1.5–2.7 tokens**; mean |ΔL_A| ≈ **0.3–0.5 tokens**.

Without this, an apparent "confidence transfer" could be a length-mismatch artifact.

### 7.4 Procedure

For each (layer, position, condition):

1. Run the donor trial clean; cache its residual stream at (layer, position).
2. Run the recipient trial with that donor activation **replacing** the recipient's own activation
   at exactly that (layer, position).
3. Compute all three metrics relative to the recipient's clean run.

Positions: **PANL** (main), **CC**, **PANL+1 (control)**. Layers: §2.9 sweep.

### 7.5 Expected results

At **PANL**, peaking at **layer 26**, evident across **all three metrics**:

| Condition | Confidence change | Logit-diff change | Token change rate |
|---|---|---|---|
| **L→H** | **≈ +0.21** (increase) | ≈ −1.2 | ≈ **37%** |
| **H→L** | **≈ −0.08 to −0.10** (decrease) | ≈ **−2.0** (largest) | ≈ **30%** |
| H→H (control) | ≈ 0 | ≈ −1.1 | ≈ 15% |
| L→L (control) | ≈ 0 | ≈ −0.3 | ≈ 12% |

- At **CC**: the **same pattern at later layers** — the temporal precedence again.
- At **PANL+1**: **no effects**.

**How to interpret / validate.**

1. The critical comparison is **cross- minus same-confidence**, not cross- versus zero. Some
   disruption from any swap is expected and is exactly what H→H / L→L quantify.
2. **Directionality** is the payload: H→L lowers confidence, L→H raises it. Generic content
   disruption cannot produce opposite-signed, donor-dependent shifts.
3. This **rules out the alternative that PANL merely encodes content features correlated with
   confidence** — recipient content is untouched.
4. **Asymmetry is expected in some settings.** On MMLU and in Magistral, the **L→H direction
   dominates**, plausibly because those confidence distributions are concentrated at the top,
   creating a ceiling for high-confidence recipients and leaving low→high as the informative test.
   Do not treat asymmetry as a failed replication; treat symmetric effects on TriviaQA + Gemma and
   L→H-dominant effects on MMLU/Magistral as the expected pattern.

**Cross-model peak layers:** Gemma categorical PANL L26 / PANL+1 L31 / CC L61; Gemma numeric PANL
L26 / PANL+1 L31 / CC L61; Qwen PANL L15 / PANL+1 L15 / CC L27.

---

## 8. Experiment 5 — Out-of-distribution control analysis

> **Question:** Do the causal interventions merely push the residual stream out of distribution,
> producing generic disruption rather than manipulation of a meaningful representation?
> **Key result:** No. All interventions stay within natural activation variability, and PANL's
> drift is indistinguishable from PANL+1's — yet only PANL produces causal effects.

This is a **mandatory control**, not an optional extra. Run it or your causal claims are not
supported.

### 8.1 Procedure

1. From the **3,000-trial activation-collection set**, compute the **natural pairwise variability**
   of activations at each position: for many random *pairs* of trials, compute
   - cosine similarity between their residual-stream activations at that (layer, position), and
   - the ratio of their L2 norms.
   Take the **5th and 95th percentiles** of each.
2. For each intervention type, compute the same two quantities between the **perturbed** and
   **unperturbed** activation at **layer 25** (the peak-effect layer):
   - **Steering:** clean vs steered activation.
   - **Patching:** clean-cached vs corruption-propagated activation ("pre-patch" similarity).
   - **Noising:** clean vs mean-replacement activation.
3. Compare intervention-induced drift against the natural distribution, **at both PANL and
   PANL+1**.

### 8.2 Expected results (Layer 25)

**Natural distribution:** cosine [p5, p95] = **[0.997–0.998, 1.000]**; norm ratio [p5, p95] =
**[0.90, 1.10–1.11]**.

**A. Activation steering**

| Position | Direction | Cosine sim | Norm ratio |
|---|---|---|---|
| PANL | High (α=2) | 0.999 | 0.96 |
| PANL | Low (α=2) | 0.999 | 1.04 |
| PANL | High (α=5) | 0.992–0.999 | 0.91–1.04 |
| PANL | Low (α=5) | 0.994–0.998 | 0.96–1.10 |
| PANL+1 | (all four) | 0.993–0.999 | 0.91–1.10 |

**B. Activation patching**

| Position | Role | Pre-patch cosine | Pre-patch norm ratio |
|---|---|---|---|
| PANL | Causal | **0.999** | 0.94 |
| PANL+1 | Control | **0.999** | 0.98 |

**C. Activation noising**

| Position | Role | Cosine sim | Norm ratio |
|---|---|---|---|
| PANL | Causal | **0.999** | 0.995 |
| PANL+1 | Control | **0.999** | 0.999 |

### 8.3 Interpretation

- Across **all three** intervention types, cosine similarity to clean activations **exceeds 0.99**
  and norm ratios stay within **0.91–1.10** — well inside the natural pairwise distribution.
- **The dissociation is the argument.** At layer 25 in the patching experiment, PANL and PANL+1
  have **nearly identical** pre-patch cosine similarity (0.999 at both), yet patching at PANL
  yields **24.3% confidence recovery** while PANL+1 yields **−1.4%** (i.e. none). OOD drift is
  comparable; causal effect is not. Therefore the effects are not OOD artifacts.
- Additional mitigation: **five mechanistically distinct intervention techniques** (steering,
  patching, noising, swap, attention blocking), each perturbing the residual stream differently,
  all converge on the same conclusion.

---

## 9. Experiment 6 — Linear probing and variance partitioning

> **Questions:** (a) Is confidence information decodable from PANL at *earlier* layers than CC?
> (b) Do PANL representations merely summarize token log-probabilities, or reflect a distinct
> computation?
> **Key result:** (a) Yes. (b) A distinct computation — PANL activations at L40 explain **38%
> unique variance** beyond **all six** log-probability baselines combined, which themselves
> explain only **10%**.

Causal interventions test sufficiency/necessity; probing reveals **where information first becomes
decodable** and **what kind** of information it is.

### 9.1 Probing procedure

**Data:** activations from **3,000 TriviaQA trials** (the activation-collection set).

**Positions probed:** PANL, PANL+1, CC, FCC, **intermediate tokens** (specifically, the first token
of each of the ten confidence classes as they appear in the *instruction* portion of the prompt),
and a **control position: the third question token (QTT)**. Also AC (Experiment 7).

**Layers:** all layers (or the §2.9 sweep, extended — the figures show the dense 0–61 axis).

**Two probe targets, per (layer, position):**

| Target | Model | Metric |
|---|---|---|
| **Answer correctness** (binary) | **L2-regularized logistic regression** | **AUROC** |
| **Verbal confidence magnitude** (continuous, class **midpoints**) | **Ridge regression** | **R²** |

**Protocol:** **5-fold cross-validation**; **all activations z-scored prior to fitting**; report
cross-validated metrics.

```python
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_predict, KFold
from sklearn.metrics import roc_auc_score, r2_score

kf = KFold(n_splits=5, shuffle=True, random_state=0)

# correctness → AUROC
clf = make_pipeline(StandardScaler(), LogisticRegression(penalty="l2", max_iter=2000))
p = cross_val_predict(clf, X, y_correct, cv=kf, method="predict_proba")[:, 1]
auroc = roc_auc_score(y_correct, p)

# confidence midpoint → R²
reg = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
pred = cross_val_predict(reg, X, y_conf_midpoint, cv=kf)
r2 = r2_score(y_conf_midpoint, pred)
```

### 9.2 Log-probability baselines (extraction)

From **Phase 0 generation**, for each trial, compute `log p(t_i | t_<i, x)` for every generated
token, then restrict to the **answer span** (identified by mapping the extracted answer string back
onto the generated token sequence). Compute **six** summaries:

1. **Length-normalized mean**: $\bar{\ell} = \frac{1}{n}\sum_{i=1}^{n} \log p(t_i \mid t_{<i}, x)$
2. **Minimum** per-token log-prob across the n answer tokens
3. **Maximum** per-token log-prob
4. **Variance** of per-token log-probs
5. Log-prob of the **first** answer token
6. Log-prob of the **last** answer token

Length-normalizing the mean controls for answer-length variation, so longer answers are not
penalized simply for having more tokens.

### 9.3 Variance partitioning procedure

For each (layer, position), fit **three** cross-validated Ridge regressions (**K = 5 folds**,
**α = 1.0**, all features **z-scored**) predicting the verbal-confidence midpoint:

- **R²_act** — activations alone (residual stream at that layer/position)
- **R²_base** — log-probability baselines alone (either one of the six, or all six concatenated)
- **R²_both** — activations and baselines concatenated

Then:

$$R^2_{\text{unique}} = \max\!\left(0,\; R^2_{\text{both}} - R^2_{\text{base}}\right)$$

i.e. the gain in predictive power from adding activations to a regression that **already** contains
the log-probability baselines.

Run the partitioning **twice**: (a) against each of the six baselines **individually**, and
(b) against **all six combined** into a single regression. The combined-baseline analysis is the
**most conservative** test, since it credits the baselines with any redundant linear information
shared across the six summaries.

### 9.4 Auxiliary correlation diagnostics

Compute, as scalar sanity checks:

- correlation between length-normalized answer log-probs and **Phase-0** (same-run) verbal
  confidence;
- correlation with **Phase-1** (different run, identical questions, answers provided in prompt)
  verbal confidence;
- correlation between Phase-0 and Phase-1 confidence ratings (a stability check).

### 9.5 Expected results

**Probing — decodability:**

| Position | Correctness AUROC (peak) | Confidence R² (peak) | Notes |
|---|---|---|---|
| **PANL** | ≈ **0.80–0.83**, rising **early** (already ~0.75 by L15–20) | ≈ **0.45**; ~**0.75** in the AC-comparison analysis | **Earliest** of all positions |
| **CC** | ≈ 0.80–0.83, rising **late** | ≈ **0.80** (highest, late layers) | Later onset |
| PANL+1 | ≈ 0.80 | ≈ 0.35–0.45 | Decodable despite being causally inert |
| FCC | ≈ 0.80 | ≈ 0.45 | Same |
| Intermediate tokens | ≈ 0.75–0.83 | ≈ 0.3–0.6 | Widespread |
| **QTT (control)** | ≈ **0.50** (chance) | ≈ **0.00** | Must be null |
| **AC** | — | ≈ **0.2** (weak) | See §10 |

**Reference horizontal lines:**
- **Verbal confidence itself** as a correctness predictor: **AUROC = 0.71**
- **Mean answer log-probability** as a correctness predictor: **AUROC = 0.75**

**Variance partitioning — the headline numbers:**

| Quantity | Value |
|---|---|
| Length-normalized mean log-prob → verbal confidence (cross-run) | r = **0.29**, R²_CV = **0.084** |
| Length-normalized mean log-prob → verbal confidence (within-run, Phase 0) | r = **0.23**, R²_CV = **0.049** |
| **All six** log-prob baselines combined → verbal confidence | r = **0.32**, R²_CV = **0.100** |
| **PANL activations at L40, R²_unique beyond all six baselines** | **0.380** |
| Phase-0 vs Phase-1 confidence consistency | r = **0.63**, R²_CV = **0.40** |

**Individual baseline R²_CV** (each alone, predicting verbal confidence):

| Baseline | R²_CV |
|---|---|
| **min** per-token log-prob | **0.101** |
| **mean** (length-normalized) | **0.084** |
| **first** answer token | **0.070** |
| **variance** of per-token log-probs | **0.051** |
| **last** answer token | **0.039** |
| **max** per-token log-prob | **0.025** |
| **all six combined** | **0.100** |

Note that the six combined (0.100) barely exceed the best single one (0.101) — they carry
**substantially overlapping** linear information.

**R²_unique curves:** PANL rises from ~L20, peaking ≈ **0.38–0.45** around L40 then declining
slightly; CC rises later (from ~L30) to ≈ **0.65** at L55–61.

### 9.6 Interpretation

1. **Temporal precedence, non-causally.** Both correctness and confidence magnitude are decodable
   from **PANL at earlier layers than from CC** — an independent confirmation of the cached
   retrieval ordering using a method (probing) that makes no causal intervention at all.
2. **Not a log-prob readout.** PANL activations explain **~38% unique variance** on top of the
   most conservative possible log-probability baseline — **more than three times larger** than the
   variance explained by any individual log-probability summary. Verbal confidence is **not
   reducible to token-level probability signals**, whether measured as mean, extremes,
   variability, or position-specific values. This is the core evidence for the **second-order**
   account.
3. **The calibration paradox, explained.** Mean answer log-prob is a *better* correctness
   predictor (AUROC 0.75) than the verbal report (0.71) — yet the verbal report is not computed
   *from* the log-probs. The model has generation-fluency evidence available and largely doesn't
   use it for verbalized confidence; it uses a distinct evaluation of question–answer fit.
4. **Probing ≠ causal relevance — state this explicitly in your write-up.** Correctness and
   confidence information is decodable **throughout** the model, including at sites where steering
   and patching have **no effect** (PANL+1, FCC). This is consistent with a long line of work
   showing information can be present in networks and detected by decoding without being used
   behaviorally, and with warnings against over-interpreting probes absent complementary causal
   interventions. **Probing alone would not have established the paper's claims** — the
   combination is what does.

---

## 10. Experiment 7 — The answer-colon (AC) control experiments

> **Question:** Is verbal confidence generated by the same machinery that produces the answer?
> **Key result:** No. Steering, patching, and noising at AC are all **null**, indistinguishable
> from the PANL+1 control, on the *same trials* where PANL shows substantial effects.

### 10.1 Why AC is the decisive first-order test

The **answer-colon (AC)** is the **last token of the Phase-0 prompt**, immediately preceding answer
generation. It is **causally implicated in answer generation**: its residual stream at the final
layer is directly transformed by the unembedding matrix to produce the logits over the first
answer token. So AC is, by construction, where generation-time evidence (including answer
log-probability information) lives.

**Under a first-order account** — verbal confidence is a readout of token log-probabilities, the
same signals that drove answer generation — **interventions at AC should modulate verbal
confidence.**

### 10.2 Procedure

Run **all four** analyses at AC, on the **same trials** used for the corresponding PANL analyses:

1. **Activation steering at AC** — identical protocol to §4, with AC as the target position.
2. **Activation patching at AC** — with one modification: **corrupt the AC token in addition to
   the answer tokens**, then patch at AC vs. at PANL. (Because AC precedes the answer, corrupting
   only answer tokens leaves AC clean; you must corrupt AC to make the restore test meaningful.)
3. **Activation noising at AC** — identical protocol to §6.
4. **Linear decoding at AC** — layerwise cross-validated **Ridge R²** for verbal confidence at AC,
   PANL, and PANL+1. **Methodological detail:** select the best Ridge α (penalty strength) for the
   **AC** position, and then **use that same α for PANL and PANL+1** — this deliberately biases
   the comparison *in AC's favour*, so that AC's weakness cannot be an artifact of hyperparameter
   selection.

### 10.3 Expected results

| Analysis | AC | PANL (same trials) |
|---|---|---|
| Steering | **No significant confidence change** | Substantial |
| Patching | **No recovery** | Partial recovery |
| Noising | **No disruption** — comparable to PANL+1 | Partial disruption |
| Decoding (Ridge R²) | **≈ 0.2** across layers | **≈ 0.75** |

### 10.4 Interpretation

- AC is **quantitatively weak** (R² ≈ 0.2 vs ≈ 0.75) *and* **causally inert** for verbal confidence.
- The weak residual signal at AC plausibly *does* include information about answer log-probability
  and other generation-time features — precisely because AC produces the first answer token. So
  the finding is not "AC contains nothing"; it is that **the model has access to generation-time
  evidence at AC but does not primarily draw on it for verbal confidence reports.**
- The richer, causally engaged confidence representation emerges **later, at the post-answer
  position** — supporting a **second-order** account in which verbal confidence reflects an
  evaluation of question–answer fit that is **computationally distinct from generating the answer
  itself**.
- Note the consistency with §4: steering at the **answer-colon** is ineffective, and steering at
  the **first answer token** is ineffective, while steering at the **last answer token** (after the
  full question and most of the answer are encoded) is effective but content-confounded.

---

## 11. Experiment 8 — Attention blocking (attention knockout)

> **Questions:** (1) Can we exclude JIT computation at CC via attention to question/answer tokens?
> (2) How does confidence flow from PANL to CC? (3) How does confidence reach PANL in the first
> place?
> **Key result:** answer tokens → PANL (L22–28) → CC (L30–36). JIT ruled out.

### 11.1 Method — attention knockout

Following Geva et al. (2023). For a **source** position `s` and **target** position `t`, set the
attention weight `α_{t←s} = 0` **across all attention heads** within a specified **layer range**,
preventing information from flowing from `s` to `t` at those layers.

**Implementation.** Requires `attn_implementation="eager"` so the attention probabilities are
materialized and hookable. Easiest robust implementation: add `−∞` to the pre-softmax attention
scores at the `(t, s)` entries via a custom additive attention mask, per layer in the target range.

```python
# additive mask of shape (batch, 1, q_len, kv_len), added to attention scores pre-softmax
mask = torch.zeros(1, 1, seq, seq, device=dev, dtype=dtype)
for t in target_positions:
    for s in source_positions:
        mask[0, 0, t, s] = torch.finfo(dtype).min      # block edge t <- s
# apply only for layers in [lo, hi); leave all other layers untouched
```

Verify by asserting that, for a blocked layer, the post-softmax attention from `t` to `s` is
numerically zero.

### 11.2 The layer-window convention (important, and different from other experiments)

Attention blocking is **not** applied at a single layer. It is applied across a **window of 12
consecutive layers centered at each x-axis position.** So a point plotted at "layer 30" means
attention was blocked across roughly layers 24–35. The x-axis in the paper's figures uses the
positions: `10, 15, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 45, 50, 56`.

Blocking single layers is insufficient because the pathway is redundant across nearby layers.

### 11.3 Which prompt to use, and why it matters

**Use the minimal numeric (0–9) prompt (§2.5.3) for the primary analysis.**

The full categorical prompt has **more than a hundred** intermediate template tokens between PANL
and CC. Confidence information cached at PANL can reach CC through **multiple redundant multi-hop
routes** via those tokens, so blocking the *direct* CC→PANL edge alone does nothing — the effect
is **masked**. The minimal prompt collapses the intermediate tokens, exposing the direct pathway.

Run **both** prompts: the minimal prompt for the pathway result, the categorical prompt as a
complementary/convergent experiment.

**Calibration check for the minimal prompt** (separate set of 2,000 questions): **ECE = 0.17**,
**AUROC = 0.68** — confirming the presence of a meaningful confidence signal suitable for
mechanistic analysis before you analyze pathways through it.

### 11.4 Conditions — minimal numeric prompt

**n = 500 trials.** Positions: PANL (the newline following the answer), PANL+1 (control), CC (the
final token before confidence generation).

| Pathway blocked | Tests |
|---|---|
| **CC → Q + A** | Whether CC computes confidence **just-in-time** by attending to question and answer tokens |
| **CC → PANL** | Whether CC **retrieves** cached confidence from PANL |
| **CC → PANL+1** | **Control** |
| **PANL → A** (all answer tokens) | How PANL **gathers** confidence from the answer |
| **PANL → last_A** (last answer token only) | Same, narrower |

**Metrics:** (1) first token change rate; (2) logit difference change (baseline token's logit minus
mean logit of the alternative digits, over the 10 digits 0–9).

### 11.5 Conditions — full categorical prompt (complementary)

Notation: `NL` = PANL, `NL+1` = PANL+1, `A` = all answer tokens, `last_A` = last answer token,
`Q` = all question tokens, `ALL` = all downstream tokens. `_keepNL` means the pathway is blocked
**except** that PANL is still allowed to attend to the answer tokens — the crucial dissociation.

Conditions: `CC→NL+1`, `CC→NL`, `CC→A`, `CC→Q`, `CC→Q+A`, `ALL→NL`, `ALL→last_A`,
`ALL→NL+last_A`, `ALL→last_A_keepNL`, `ALL→A`, `ALL→NL+A`, `ALL→A_keepNL`.

### 11.6 Expected results — minimal numeric prompt

| Pathway | First-token change rate | Logit diff change | Peak layers |
|---|---|---|---|
| **CC → PANL** | **peaks ≈ 21%** | **≈ −0.80** (marked reduction) | **L30–36** |
| CC → Q + A | ≈ **10%** — **indistinguishable from control** | ≈ −0.2 (small) | — |
| CC → PANL+1 (control) | ≈ **10%** | ≈ 0 | — |
| **PANL → A** | **≈ 20%** | **≈ −0.85** | **L22–28** |
| **PANL → last_A** | **≈ 20%** | **≈ −0.75** | **L22–28** |

### 11.7 Expected results — full categorical prompt

| Condition | First-token change rate | Logit diff change |
|---|---|---|
| CC→NL+1 (control) | ≈ 10% | ≈ 0 |
| CC→NL | ≈ 9% (**null** — masked by redundant routing) | ≈ −0.3 |
| CC→A | ≈ 12% | ≈ −0.2 |
| CC→Q | ≈ 11% | ≈ −0.2 |
| CC→Q+A | ≈ 12% | ≈ −0.4 |
| **ALL→NL** | **≈ 18–20%** | ≈ −0.9 |
| **ALL→last_A** | **≈ 50%** (figure ≈ 51%) | ≈ **−5.3** |
| ALL→NL+last_A | ≈ 48% | ≈ −5.3 |
| **ALL→last_A_keepNL** | **reduced to ≈ 20–24%** | ≈ −1.6 |
| **ALL→A** | **≈ 67–70%** | ≈ **−8.0** |
| ALL→NL+A | ≈ 59% | ≈ −7.3 |
| **ALL→A_keepNL** | **reduced to ≈ 40–51%** | ≈ −4.3 |

### 11.8 Interpretation — the three conclusions

1. **CC does not compute confidence from scratch (JIT ruled out).** Blocking CC's attention to
   question and answer tokens produces effects **indistinguishable from the PANL+1 control**
   (~10% change rate) — in **both** prompts. If CC were integrating question/answer information de
   novo, severing that access would be catastrophic. It isn't.
2. **CC retrieves confidence information from PANL.** In the minimal prompt, blocking CC→PANL
   produces **substantial** disruption (~21%, L30–36), **significantly exceeding** the PANL+1
   control. The categorical prompt's null on this edge is explained by redundant routing, and the
   `ALL→NL` result (~20% change) confirms PANL is a cache even there.
3. **PANL reads confidence from answer tokens.** Blocking PANL→A or PANL→last_A produces ~20%
   change rates at **earlier** layers (**L22–28**), **preceding** the CC→PANL effect by
   **approximately 6–8 layers**. The `_keepNL` conditions are the cleanest demonstration: blocking
   everything downstream from attending to the answer produces a 50%/70% change rate, but
   **preserving only the PANL→answer pathway cuts that to 20%/40%** — PANL reads confidence-
   relevant information from answer tokens and relays it downstream.

**Sequential flow established: answer tokens → PANL (L22–28) → CC (L30–36) → unembedding (L61).**

### 11.9 Methodological caveat you must carry into your write-up

Following Geva et al. (2023): **this method does not account for information that may have already
passed between positions at earlier layers, prior to the blocking intervention.** Therefore:

- **Null results should be interpreted cautiously** (they may reflect redundancy or earlier
  transfer, not absence of a pathway) — this is exactly what happened with CC→PANL in the
  categorical prompt.
- **Positive results provide evidence** that the blocked pathway carries task-relevant information
  at the targeted layers.

---

## 12. Experiment 9 — Generalization suite

The paper replicates along **four axes**. Each is a re-run of Experiments 1–4 (and, where noted,
6) with a substituted component. The invariant to check in every case:

> **PANL plays a specific, causally sufficient role in verbal confidence generation, distinct from
> the immediately adjacent control position (PANL+1), with temporal precedence over CC wherever
> layer-wise analyses are performed.**

### 12.1 Axis 1 — Numeric (0–100) confidence prompt, Gemma 3 27B, TriviaQA

**Setup.** Prompt from §2.5.2. `max_new_tokens = 4` (to generate the full value, e.g. "95").
Positions PANL, PANL+1, FCC, CC are **analogous to their positions in the categorical prompt**.

**Metrics (numeric analogues):**

- **Confidence change** = integer (0–100) in baseline condition minus integer in intervened
  condition.
- **First digit change rate** = proportion of trials where the first generated digit differs from
  clean — analogous to first-token change rate.
- **Logit difference** = logit of the clean trial's first digit minus the **mean logit of the other
  nine digits (0–9)**.

**Multi-token / KV-cache caveat (must be documented).** Numeric confidence is **multi-token**
(e.g. "95"). **All interventions occur during prefill**, modifying cached key-value
representations that subsequent digits attend to. The second digit is generated by attending to
**both** the cached prompt **and** the first digit — so effects on later digits reflect **both** the
original intervention **and** changes propagated through earlier generated tokens. Prefer the
first-digit metrics for clean causal attribution.

**Expected:** calibration ECE = 0.16, AUROC = 0.73 (n = 8,008). Baseline confidence 0.54. Steering
peaks PANL L25 / PANL+1 L31 / CC L31; patching PANL L25 / PANL+1 L0 / CC L40; noising PANL L26 /
PANL+1 L26 / CC L61; swap PANL L26 / PANL+1 L31 / CC L61. Steering Δconfidence on the 0–100 scale:
PANL high ≈ +20, low ≈ −7; CC high ≈ +37, low ≈ −7. Steering is n = 124 trials per condition per
layer for the numeric-prompt figure.

### 12.2 Axis 2 — Qwen 2.5 7B Instruct, categorical prompt, TriviaQA

**Setup.** `Qwen/Qwen2.5-7B-Instruct` via Hugging Face, eval mode, greedy (temperature 0).
**28 layers**; **dense layer sweep across layers 0–27**. Same TriviaQA subset as Gemma, **3,000
trials for activation collection**. Same procedures as Gemma throughout.

**Trial-pool adjustment.** Because of Qwen's confidence distribution, **low-confidence trials are
sampled from the "Unlikely" class and high-confidence trials from the "Likely" class** (rather
than the top-3/bottom-3 bands).

**Trial counts (differ from Gemma):**

| Experiment | n |
|---|---|
| Steering | **150** questions per condition per layer |
| Patching | **200** questions |
| Noising | **300** questions (200 high-confidence, 100 low-confidence) |
| Swap | **200** questions per condition |

**Expected:** ECE = **0.06**, AUROC = **0.65**, baseline confidence 0.56. Peak layers: steering
PANL L15 / PANL+1 L1 / CC L22; patching PANL L15 / PANL+1 L27 / CC L27; noising PANL L11 /
PANL+1 L6 / CC L21; swap PANL L15 / PANL+1 L15 / CC L27. **Comparable effects to Gemma in all
four experiments except activation steering, where effects are stronger in Gemma.**

### 12.3 Axis 3 — Additional datasets (BigMath, MMLU), Gemma 3 27B, categorical prompt

Re-run patching, noising, and swap (and the confidence-distribution analysis) on each dataset,
using exactly the Gemma categorical protocol with the dataset's questions substituted.

| Dataset | Accuracy | Notes |
|---|---|---|
| **BigMath** | **40.2%** correct | Broader confidence distribution than MMLU; swap shows both directions |
| **MMLU** (multiple-choice) | **76.8%** correct | **Primarily high-confidence responses**; swap effects are **asymmetric, L→H dominant** (H→L near ceiling); the L→H trend may be visible but **not significant** |

**Expected pattern (both):** patching at PANL recovers confidence and logit difference while
PANL+1 does not; noising at PANL changes the first token while PANL+1 does not; cross-confidence
swaps at PANL shift confidence beyond same-confidence controls while PANL+1 shows nothing.

### 12.4 Axis 4 — Reasoning model: Magistral Small 2506 (24B, 40 layers), TriviaQA

This is the most involved replication because a **chain-of-thought trace intervenes between the
question and the final answer.**

**Model.** `mistralai/Magistral-Small-2506`, dense decoder-only, 24B params, **40 layers**, loaded
from HF with **`attn_implementation="eager"`** (to enable attention-weight access), **max tokens
1024**, **greedy decoding**.

**Behavioral run.** **5,000** TriviaQA questions → **N = 4,998** after filtering for valid answers
and valid confidence classifications.

**Two-phase prompting.** Phase 1 = CoT answer prompt (§2.5.4); Phase 2 = confidence prompt with the
**full reasoning trace plus extracted answer** presented back inside the response block (§2.5.5).

**Activation set.** Sample a **stratified subset of 3,000 trials**: **retain all trials with verbal
confidence ≤ 0.7**, then fill the remainder by random sampling from high-confidence trials — this
preserves the limited pool of low-confidence trials needed for H/L contrasts. (**92% of Magistral's
responses are "Almost certain".**)

**Position definitions.** **PANL = the newline token terminating the response block** (after the
extracted answer); **PANL+1 = the subsequent token**; **CC = the very last token of the whole
prompt** (after `**Confidence**:`); **ALT = last token of the final answer**; **QTT = third
question token** (control); **Trace k%** = tokens sampled at 10% increments across the whole
reasoning trace, from trace start to the final answer token within the response block ("Trace 100%"
is the very last token of the trace, usually a period).

**Common adaptations (all three causal experiments):**

- Trial selection draws from the **extremes of the confidence distribution (sorted by midpoint)**
  rather than uniformly within each high/low band — the cleanest available contrast given the 92%
  concentration.
- The **logit difference metric tracks the clean trial's predicted confidence-class token across
  all intervention conditions (a fixed target)**, rather than the argmax of each condition.

**Activation patching.** Corrupt-then-restore as in §5, but the **corruption scope changes**: in
the non-CoT setting confidence-relevant content is concentrated in the short answer string, but
under CoT it is **distributed across the full reasoning trace**. Therefore corrupt the embeddings
of **all tokens spanning the question and the entire response block (reasoning trace plus final
answer string)**, **excluding the PANL newline itself and all downstream classification tokens.**

**Activation noising.** Mean ablation as in §6. Mean activations collected at PANL and PANL+1 from
a **100-trial calibration set (50 highest + 50 lowest confidence)**. Test set **n = 400** (200
lowest-confidence + 200 highest-confidence), **shuffled**. **CC is tested as a control position
rather than a primary position**, given its near-certain ceiling.

**Activation swap.** 2×2 factorial as in §7. Recipient pool: **400 high + 400 low**, selected from
the extremes. **Donors length-matched to recipients on both question length and reasoning-trace
length using 10-quantile bins on each axis.** Swaps performed at **PANL and PANL+1**.

**Decoding.** Collect activations at the **10 trace positions** plus the **five standard positions**
(PANL, PANL+1, CC, last answer token, third question token). Probing methodology follows the main
experiments — **ridge regression for verbal confidence, 5-fold cross-validated R²**.

**Expected results:**

| Analysis | Result |
|---|---|
| **Patching** | **Substantial recovery at PANL**; **no effect at PANL+1**. Replicates Gemma. |
| **Noising** | **No effect at PANL** beyond the PANL+1 control — **a dissociation from Gemma**. But **noising at CC produces substantial disruption.** |
| **Swap** | Cross-confidence swaps at PANL (L→H and H→L) produce **systematic directional shifts** beyond same-confidence controls; **no effect at PANL+1**. **L→H dominates** (ceiling effect for high-confidence recipients). |
| **Decoding** | Confidence decodable from **PANL** (peak-layer R² comparable to the final trace token), from **CC at later layers**, and **increasingly across the reasoning trace, peaking at the final trace token immediately preceding the answer**. **QTT control explains negligible variance.** |

**How to interpret the noising dissociation (do not treat it as a failure to replicate).** Patching
works at PANL but noising doesn't — and the decoding result explains why. In the CoT regime,
confidence-relevant information is **distributed across the reasoning trace**, especially toward
its end. That distributed encoding creates **redundant pathways**: ablating PANL alone leaves an
intact, trace-distributed signal that CC can retrieve directly. Patching, by contrast, asks a
sufficiency question that a redundant code can still answer affirmatively. So the paper's summary
is that across **patching, swap, and decoding**, Magistral supports cached retrieval — confidence
is encoded at the post-answer-newline position following the final answer, **even when that answer
is preceded by an extended reasoning trace** — with the single-position noising null attributable
to trace-distributed redundancy.

### 12.5 The generalization claim to evaluate

The pattern of **PANL playing a specific, causally sufficient role in verbal confidence generation,
distinct from immediately adjacent control positions**, held across **all prompt formats, datasets,
and non-reasoning model architectures**, with **temporal precedence over CC wherever layer-wise
analyses were performed**. In Magistral, patching, swap, and decoding similarly localized
confidence representations to PANL, with the noted noising exception.

Conclusion: cached retrieval reflects a **general computational strategy** for verbal confidence
generation in LLMs, **not** an artifact of prompt format, dataset, model architecture, or the
absence of explicit chain-of-thought reasoning.

---

## 13. Underdetermined details and recommended defaults

The paper does not fully specify the following. Each entry gives the recommended default and the
reason; document whichever choice you make, since some materially affect exact numbers (though
none should affect the qualitative conclusions).

| # | Underdetermined | Recommended default | Rationale |
|---|---|---|---|
| 1 | **TriviaQA split and config** | `validation`, `rc.nocontext` (closed-book), deduplicated on normalized question text | The prompts contain no supporting document; validation is standard and large enough for all disjoint subsets |
| 2 | **Chat template usage** | Apply each model's chat template (all three checkpoints are instruction-tuned), with the prompt as a single user turn | The models are `-it`/`-Instruct` variants; the paper shows raw prompt text but a chat template is how these models are meant to be used. **Whatever you choose, be consistent** — the template shifts all position indices |
| 3 | **Leading space on class names** | Determine empirically which first-token variant the model emits and use it consistently for all ten classes | Only requirement is that the ten first tokens are distinct and match what's generated |
| 4 | **Exact residual-stream hook point** | Output of the decoder layer (after the MLP block) | Explicitly stated for patching; applied uniformly for consistency |
| 5 | **`mean_residual_norm_at_layer` for steering** | Mean L2 norm at that (layer, position) over the activation-collection set | "3% of the residual norm at each layer" — position-conditioned is the natural reading given interventions are position-specific |
| 6 | **Ridge α for the main probing** | α = 1.0 (explicit for variance partitioning); for the AC comparison, tune α on AC and reuse it for PANL/PANL+1 (explicit) | Stated in §C.1.9 and Figure 13d respectively |
| 7 | **Logistic regression C** | scikit-learn default (C=1.0), L2 penalty | Paper says only "L2-regularized" |
| 8 | **ECE binning** | 10 bins (matches the 10 classes; 10 equal-width bins for numeric) | Natural given the class structure |
| 9 | **Number of pairs for natural-variability percentiles** | ≥100,000 random pairs from the 3,000-trial set | Enough for stable p5/p95 |
| 10 | **Quantile-bin count for donor matching (Gemma/Qwen)** | 10 bins per axis (explicit for Magistral; adopt the same for Gemma) | Paper specifies 10-quantile bins for Magistral, "quantile bins" for Gemma |
| 11 | **Statistical testing** | The paper reports SEM error bars and describes effects as "significant"/"beyond control" without naming a test. Use a paired t-test or Wilcoxon signed-rank of each condition against its control on matched trials, and report effect sizes | Makes "significantly exceeded the PANL+1 control" checkable |
| 12 | **Phase-0 prompt exact wording** | Take the categorical prompt and move the entire confidence-instruction block to the start, ending the prompt at `**Answer**:` | Paper: "essentially identical to Figure 8, except that confidence instructions appeared at the start" |
| 13 | **BigMath subset selection** | Sample to match the reported **40.2%** accuracy | Big-Math is difficulty-stratified; accuracy is the only anchor given |
| 14 | **MMLU subset/split** | `test` split, sampled across all subjects | Accuracy anchor **76.8%** |
| 15 | **Number of "intermediate token" probe positions** | The first token of each of the 10 confidence classes as listed in the instruction block | Explicit in §C.1.8 |

---

## 14. Master validation table

Use this as your replication checklist. Qualitative claims are the ones that must hold; numeric
values are targets that should be approached within a few percent given identical setup, and within
sampling noise otherwise.

### 14.1 Must-hold qualitative claims

| # | Claim | Established by |
|---|---|---|
| Q1 | Steering at **PANL** modulates verbal confidence, bidirectionally and gradedly | Exp 1 |
| Q2 | Steering at **PANL+1** and **FCC** does **not** | Exp 1 |
| Q3 | PANL effects peak at **earlier layers** than CC effects — in steering, patching, noising, swap, and probing | Exps 1, 2, 3, 4, 6 |
| Q4 | Patching **PANL** partially recovers confidence after answer corruption; **PANL+1** does not | Exp 2 |
| Q5 | Noising **PANL** partially disrupts confidence; **PANL+1** does not | Exp 3 |
| Q6 | **Cross-confidence** swaps at PANL shift confidence **directionally** beyond **same-confidence** controls | Exp 4 |
| Q7 | Intervention-induced OOD drift is within natural variability and **equal at PANL and PANL+1**, despite opposite causal effects | Exp 5 |
| Q8 | PANL activations explain large **unique** confidence variance beyond **all six** log-prob baselines | Exp 6 |
| Q9 | Steering / patching / noising at **AC** are all **null** | Exp 7 |
| Q10 | Blocking **CC → Q+A** has **no effect beyond control** (JIT ruled out) | Exp 8 |
| Q11 | Blocking **CC → PANL** (minimal prompt) **substantially disrupts** confidence | Exp 8 |
| Q12 | Blocking **PANL → answer tokens** disrupts confidence at **earlier layers** than the CC→PANL effect | Exp 8 |
| Q13 | The PANL-vs-PANL+1 dissociation holds across prompt formats, datasets, and architectures | Exp 9 |

### 14.2 Numeric targets

| Quantity | Target |
|---|---|
| Gemma categorical: accuracy / ECE / AUROC | 77.4% / 0.12 / 0.71 |
| Gemma numeric: ECE / AUROC | 0.16 / 0.73 |
| Gemma minimal-numeric: ECE / AUROC | 0.17 / 0.68 |
| Qwen categorical: ECE / AUROC | 0.06 / 0.65 |
| Steering peak layers, Gemma categorical: PANL / CC | **21–25** / **30–35** |
| Steering Δconfidence at PANL (α=5) | ≈ ±0.15–0.20 |
| Steering Δconfidence at CC (α=5) | ≈ ±0.40 |
| Steering baseline confidence | 0.55 |
| Patching: clean / corrupt logit diff | ≈ 11.5 / ≈ 0 |
| Patching: corrupt first-token change rate | **100%** |
| Patching peak recovery layers: PANL / CC | **L25** / **>L30** |
| Patching confidence recovery at PANL (L25) / PANL+1 | **24.3%** / **−1.4%** |
| Noising: clean logit diff | ≈ 9.4 |
| Noising peak: PANL token-change / CC token-change | ≈ 14% (L25–26) / ≈ 78% (L61) |
| Swap peak layer at PANL | **L26** |
| Swap: L→H confidence change / H→L logit-diff change | ≈ +0.21 / ≈ −2.0 |
| OOD: cosine similarity, all interventions | **> 0.99** |
| OOD: norm ratio, all interventions | **0.91–1.10** |
| OOD: natural cosine [p5,p95] / natural NR [p5,p95] | [0.997, 1.000] / [0.90, 1.11] |
| Probing: mean-logprob AUROC for correctness | **0.75** |
| Probing: verbal-confidence AUROC for correctness | **0.71** |
| Variance partitioning: all six logprob baselines, R²_CV | **0.100** (r = 0.32) |
| Variance partitioning: single mean-logprob baseline, R²_CV | **0.084** |
| Variance partitioning: **PANL L40 R²_unique** | **0.380** |
| Individual baselines R²_CV (min/mean/first/var/last/max) | 0.101 / 0.084 / 0.070 / 0.051 / 0.039 / 0.025 |
| Logprob → confidence: within-run / cross-run | r=0.23, R²=0.049 / r=0.29, R²=0.084 |
| Phase-0 vs Phase-1 confidence consistency | r = **0.63**, R²_CV = 0.40 |
| AC decoding R² vs PANL decoding R² | ≈ **0.2** vs ≈ **0.75** |
| Attention blocking (minimal): CC→PANL peak | **≈ 21%**, L30–36 |
| Attention blocking (minimal): CC→Q+A / control | ≈ 10% / ≈ 10% |
| Attention blocking (minimal): PANL→A, PANL→last_A peak | **≈ 20%**, L22–28 |
| Layer gap between PANL→A and CC→PANL effects | **6–8 layers** |
| Attention blocking (categorical): ALL→last_A → keepNL | 50% → 20–24% |
| Attention blocking (categorical): ALL→A → keepNL | 67–70% → 40–51% |
| BigMath / MMLU accuracy | 40.2% / 76.8% |
| Magistral: n after filtering / "Almost certain" share | 4,998 / **92%** |

### 14.3 Common failure modes and what they mean

| Symptom | Likely cause |
|---|---|
| Corrupt baseline does **not** give 100% token change | Answer-span token mapping is wrong; verify by decoding the span you corrupted |
| PANL+1 shows effects comparable to PANL | You are intervening on a slice/range rather than a single position, or the newline is not an isolable token in your tokenizer |
| PANL and CC peak at the same layer | Position indices swapped, or you're not recomputing positions per trial (question/answer lengths vary) |
| All confidence classes collapse to one token id | Class-initial tokens are not unique — check the leading-space variant |
| Steering has no effect anywhere | Vector normalization wrong (check the "3% of residual norm" step), or hook applied to the wrong tuple element |
| Attention blocking has no effect anywhere | Not using `attn_implementation="eager"`, or blocking a single layer instead of a 12-layer window |
| CC→PANL blocking is null | Expected **with the categorical prompt** — you must use the minimal numeric prompt for that specific test |
| Probing AUROC ≈ 0.5 at every position | Correctness labels misaligned with trials, or activations captured at the wrong forward pass |
| Magistral PANL noising is null | **Expected** — see §12.4 |

---

## 15. Suggested execution order and compute budget

### 15.1 Order

1. **Infrastructure** — model loading, tokenization, position finding, forward-pass logit reading,
   metric functions, hook utilities. Validate the class-initial-token uniqueness assertion and the
   forward-pass-vs-generate equivalence check.
2. **Experiment 0** (behavioral + calibration + Phase 0 log-probs). *Gate:* ECE 0.12, AUROC 0.71,
   accuracy 77.4%. Do not proceed until this replicates.
3. **Activation collection** — 3,000 trials × all sweep layers × all positions, cached to disk.
   Everything downstream reads from this.
4. **Experiment 6** (probing + variance partitioning). Cheap (no extra forward passes) and it
   independently confirms the PANL-before-CC ordering, so it's a good early signal.
5. **Experiment 1** (steering) → **2** (patching) → **3** (noising) → **4** (swap).
6. **Experiment 5** (OOD control) — cheap, uses the caches from 1/2/3.
7. **Experiment 7** (AC controls).
8. **Experiment 8** (attention blocking) — needs the eager-attention reload and the minimal prompt.
9. **Experiment 9** (generalization) — the largest block; parallelize across the four axes.

### 15.2 Rough forward-pass budget (Gemma 3 27B, main experiments)

| Experiment | Forward passes |
|---|---|
| Phase 0 generation (7,858 q) | 7,858 generations |
| Phase 1 clean (7,858 q) | 7,858 single passes |
| Activation collection (3,000) | 3,000 (with caching hooks) |
| Steering: 22 layers × 6 positions × 2 directions × 2 scales × 200 | ≈ 105,600 |
| Patching: 22 layers × 3 positions × 200 (+ clean + corrupt baselines) | ≈ 13,600 |
| Noising: 22 layers × 3 positions × 400 | ≈ 26,400 |
| Swap: 22 layers × 3 positions × 4 conditions × 400 (+ donor passes, cacheable) | ≈ 105,600 |
| Attention blocking: 16 windows × 5 pathways × 500 × 2 prompts | ≈ 80,000 |

Roughly **350k single forward passes** for the Gemma main experiments, plus generation. On a single
H100 at bf16 with batching and prompt-prefix KV caching, this is on the order of a few GPU-days;
the generalization suite multiplies it by roughly 3–4×. Budget accordingly, and cache aggressively
(the clean forward pass for each trial is reused by every intervention).

### 15.3 Efficiency notes

- **Batch across trials, not across layers** — each layer needs its own hooked pass.
- **Cache the clean run once per trial** (logits over the 10 class tokens + residual streams at all
  positions of interest) and reuse it as the baseline for every intervention.
- The **prompt prefix up to the question is identical across trials**; a shared KV cache for it
  gives a large speedup, but be careful that this interacts with attention blocking (recompute
  fully for those runs).
- Store activations in float16 on CPU; the full 3,000 × 22 layers × 7 positions × 5,376-dim tensor
  is a few GB.

---

## 16. Summary of what a successful reproduction shows

Verbal confidence in LLMs reflects **cached retrieval, not just-in-time computation**. Confidence
representations emerge **automatically during answer generation** — before the model has any way of
knowing a rating will be requested — at the first post-answer position, are gathered there from
answer tokens (particularly the last answer token) at layers 21–28, routed to the verbalization
site (directly, or through intermediate template tokens), persist there through layers 30–36, and
are transformed into output by the unembedding matrix at the final layer.

And those cached representations are **not** a readout of token log-probabilities: six different
log-probability summaries of the answer span jointly explain only ~10% of verbal-confidence
variance, while the PANL representation explains ~38% *beyond* them — and the position that
actually produces the answer (AC) is causally inert for confidence. Verbal confidence is therefore
a **sophisticated, automatic self-evaluation of question–answer fit**, computationally distinct
from generating the answer — a **second-order** rather than first-order confidence architecture,
which is precisely the kind that can in principle support **error detection** (recognizing an
answer may be wrong after committing to it).

Two caveats the authors themselves attach, which a faithful reproduction should preserve:
cached retrieval is the **dominant** rather than the **sole** pathway (distributed or overlapping
circuits likely also contribute, especially in untested regimes); and the prompt wording is **fixed
within each format** — sensitivity to paraphrase and to persona-style framing ("respond
uncertainly" vs "confidently") was not tested, and whether such framings act on the PANL
representation upstream or bias the verbalization stage at CC remains open.
