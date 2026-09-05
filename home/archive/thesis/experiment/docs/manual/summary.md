# Experiment Summary

## *How do LLMs Compute Verbal Confidence?* (Kumaran, Conmy, Barbero, Osindero, Patraucean & Veličković, ICML 2026)

Condensed digest of the experiments specified in `reproduction-guidebook.md`. For exact
prompts, hyperparameters, and reproduction procedure, see that file.

---

## 1. Paper at a glance

Two questions, each with two competing accounts:

- **Q1 — *When* is confidence computed?** Just-in-time (only at the confidence prompt) vs.
  cached retrieval (computed automatically during/after answer generation, stored at an
  answer-adjacent position, retrieved later).
- **Q2 — *What* does confidence represent?** First-order (a readout of the same signal that
  picked the answer, i.e. token log-probabilities) vs. second-order (a distinct evaluation of
  question–answer fit).

**Answers the experiments below establish:** cached retrieval wins, second-order wins.
Confidence is consolidated at the post-answer newline (PANL, layers ~22–28), routed to the
confidence-colon verbalization site (CC, layers ~30–36), and is causally and statistically
distinct from token log-probabilities — this holds across prompt format, three datasets, two
architectures, and a reasoning model with an explicit chain of thought.

---

## 2. Shared setup

- **Models:** Gemma 3 27B IT (primary, 62 layers), Qwen 2.5 7B Instruct (28 layers,
  architecture generalization), Magistral Small 2506 24B (40 layers, reasoning-model
  generalization). GPT-4o-mini grades free-text correctness and screens for hedging language.
- **Datasets:** TriviaQA (primary, closed-book), Big-Math and MMLU (generalization only).
- **Two-phase protocol:** *Phase 0* — model answers the question (confidence instructions
  moved to the prompt's start). *Phase 1* — the question is re-presented with the model's own
  Phase-0 answer inserted, and a confidence rating is elicited. Because a transformer's forward
  pass is a pure function of preceding tokens, Phase 1 reproduces exactly the activations
  autoregressive generation would have produced — enabling cheap, cacheable, single forward
  passes instead of full sampling for every intervention.
- **Prompt engineering trick:** the ten confidence classes are chosen so each has a unique
  first token, so one forward pass (not generation) reads off the confidence class.
- **Key token positions:**
  - **AC** (answer-colon) — last token before the answer is generated; feeds the unembedding
    for the first answer token. Tests the first-order account.
  - **PANL** (post-answer newline) — immediately after the answer, before any confidence
    instructions exist in-context. **Primary hypothesized cache site.**
  - **PANL+1** — one token after PANL. **Primary control** (should always be null).
  - **FCC** — colon inside the confidence-instruction block. Secondary control.
  - **CC** (confidence-colon) — the very last prompt token. **Verbalization site.**
  - **QTT** — third question token. Control for probing.
- **Metrics used throughout:** logit difference (and its change), confidence change (class
  midpoint), first-token change rate, percent recovery (patching), ECE/AUROC (calibration),
  SEM error bars.
- **Five intervention techniques**, all operating on the residual stream after a decoder
  layer's MLP block: steering (add a vector), patching (restore clean value into corrupted
  run), noising (mean-ablate), swap (transplant another trial's activation), attention
  blocking (zero attention edges). Convergence across all five is the paper's main safeguard
  against any single technique's artifacts.

---

## 3. Experiments

### Experiment 0 — Behavioral baseline & calibration
**Question:** Does the model produce a meaningful confidence signal at all?
**Method:** Run both phases on ~7,858 (categorical) / 8,008 (numeric) TriviaQA questions;
grade correctness with GPT-4o-mini; compute accuracy, ECE, AUROC.
**Result:** Gemma categorical — 77.4% accuracy, ECE 0.12, AUROC 0.71 (confidence distribution
skewed high). Mean answer log-probability alone reaches AUROC 0.75 — *better* than the verbal
report, foreshadowing that confidence isn't just a log-prob readout. Hedging language ≈ 0%.
**Establishes:** a real, if imperfect, calibration signal worth explaining mechanistically —
the prerequisite for every later experiment.

### Experiment 1 — Activation steering
**Question:** *Where* (layer × position) is confidence represented?
**Method:** Build high/low confidence direction vectors from the 25 most/least confident
correct trials; add them (scaled to 3% of residual norm × α∈{2,5}) at one position/layer at a
time; measure Δconfidence.
**Result:** Strong, bidirectional, graded effect at **PANL (peak L21–25)** and at **CC (peak
L30–35)**; PANL+1, FCC, first-answer-token, and **AC all null**. Last-answer-token works but is
confounded with answer content.
**Establishes:** falsifies just-in-time (PANL has a dedicated effect); the PANL-before-CC
layer ordering is the first sign of cached retrieval.

### Experiment 2 — Activation patching (corrupt-then-restore)
**Question:** Is PANL *sufficient* to drive confidence?
**Method:** Mean-ablate answer-token embeddings (destroying answer info), then restore the
clean activation at one (position, layer) at a time.
**Result:** Corrupt baseline collapses logit diff (11.5→0) and gives 100% token-change.
Restoring **PANL** partially recovers confidence (peak **L25**, ~24% recovery); restoring
**CC** gives near-complete recovery but only from **L30 onward**; **PANL+1 recovers nothing**.
**Establishes:** PANL sufficiency, with the same temporal precedence over CC; partial (not
full) PANL recovery is expected since cached retrieval is the dominant, not sole, pathway.

### Experiment 3 — Activation noising (mean ablation)
**Question:** Is PANL/CC *necessary* for confidence?
**Method:** Replace a single position's activation with the mean over a balanced 100-trial
calibration set, one layer at a time.
**Result:** PANL ablation dips logit diff modestly (peak disruption **L25–26**); CC ablation
causes steep disruption **after L30**; PANL+1 stays flat.
**Establishes:** partial necessity for PANL and CC, same ordering again. (Mean ablation
*disrupts*, it does not set confidence to "medium" — averaging high/low activations is not a
neutral midpoint.)

### Experiment 4 — Activation swap (interchange intervention)
**Question:** Does PANL carry confidence-*specific* information, or just correlated content?
**Method:** 2×2 factorial — transplant a donor trial's PANL activation into a
length-matched recipient of the same or opposite confidence band (H→H, L→L controls; H→L,
L→H cross-confidence).
**Result:** At **PANL (peak L26)**, L→H raises confidence (~+0.21) and H→L lowers it
(~−0.08 to −0.10), both exceeding same-confidence controls; same pattern recurs later at CC;
PANL+1 shows nothing.
**Establishes:** the decisive result against "PANL just encodes content" — recipient content
is untouched, yet the donor's confidence transfers directionally.

### Experiment 5 — Out-of-distribution control
**Question:** Do the interventions just push activations off-distribution, producing generic
disruption rather than manipulating a real representation?
**Method:** Compare cosine similarity / norm ratio of perturbed vs. clean activations against
the natural pairwise variability of unperturbed trials, at both PANL and PANL+1.
**Result:** All interventions stay within natural variability (cosine > 0.99, norm ratio
0.91–1.10); PANL and PANL+1 show *equally small* drift, yet only PANL produces causal effects.
**Establishes:** rules out "it's all just noise injection" — causal effects track the
representation, not generic perturbation magnitude.

### Experiment 6 — Linear probing & variance partitioning
**Question:** (a) Is confidence decodable earlier at PANL than CC? (b) Does PANL just
summarize token log-probabilities, or reflect something distinct?
**Method:** Cross-validated logistic/ridge probes per (layer, position) for correctness
(AUROC) and confidence magnitude (R²); separately, partition confidence variance into
log-probability baselines (6 summaries: mean, min, max, variance, first-token, last-token) vs.
residual-stream activations.
**Result:** PANL decodability rises earlier (correctness AUROC ~0.80 by L15–20) than CC's;
QTT control stays at chance. All six log-prob baselines *combined* explain only R²=0.100 of
confidence variance; **PANL at L40 adds 0.380 unique R²** on top of that — over 3× any single
baseline.
**Establishes:** non-causal confirmation of the PANL-before-CC ordering, and the core
statistical evidence for the second-order account. (Caveat: probing shows *decodability*, not
*causal use* — PANL+1 is also decodable despite being causally inert; only combined with the
causal experiments above does this become a real claim.)

### Experiment 7 — Answer-colon (AC) controls
**Question:** Is confidence generated by the same machinery that produced the answer
(first-order)?
**Method:** Re-run steering, patching, and noising at **AC** (the position whose final-layer
state literally produces the first answer token) on the same trials where PANL shows effects;
also decode confidence at AC with a Ridge α tuned to favor AC.
**Result:** All three interventions at AC are **null**, indistinguishable from PANL+1; AC
decoding R²≈0.2 vs. PANL's ≈0.75.
**Establishes:** rules out the first-order account directly — the position that generates the
answer is causally inert for confidence; the richer, causal representation emerges later, at
PANL.

### Experiment 8 — Attention blocking (attention knockout)
**Question:** Can CC compute confidence just-in-time from question/answer tokens, or does it
retrieve from PANL? How does information reach PANL?
**Method:** Zero attention weights across a 12-layer window for a chosen source→target edge
(requires eager attention). Primary analysis uses a minimal 0–9 confidence prompt (few
intermediate tokens, so the direct CC↔PANL edge isn't masked by redundant routing); the full
categorical prompt is run as a complementary check.
**Result:** Blocking **CC→Q+A** ≈ 10% change, indistinguishable from the PANL+1 control (JIT
ruled out). Blocking **CC→PANL** (minimal prompt) peaks ~21% change at **L30–36**. Blocking
**PANL→answer tokens** peaks ~20% change at **L22–28**, preceding the CC→PANL effect by 6–8
layers.
**Establishes:** the explicit information-flow pathway — **answer tokens → PANL (L22–28) →
CC (L30–36) → unembedding** — completing the causal story from the other three experiments.

### Experiment 9 — Generalization suite
**Question:** Is the PANL/cached-retrieval story specific to one prompt/dataset/model, or
general?
**Method:** Re-run Experiments 1–4 (and 6) across four axes: (1) numeric 0–100 confidence
prompt, (2) Qwen 2.5 7B (different architecture), (3) Big-Math and MMLU (different domains),
(4) Magistral Small 24B (reasoning model with an explicit chain-of-thought trace).
**Result:** The PANL-vs-PANL+1 dissociation and PANL-before-CC ordering hold on all four axes.
Notable deviations, both explained rather than treated as failures: MMLU/Magistral swaps are
**L→H dominant** (ceiling effect — confidence is already concentrated high); Magistral
**noising at PANL is null** even though patching and swap still work, because in a
chain-of-thought regime confidence is redundantly distributed across the whole reasoning
trace, so ablating one position leaves the signal intact elsewhere.
**Establishes:** cached retrieval is a general computational strategy for verbal confidence,
not an artifact of one prompt format, dataset, architecture, or the absence of chain-of-thought.

---

## 4. Cross-cutting conclusion

Verbal confidence is **cached, not just-in-time**: it is built automatically during answer
generation — before the model could know a rating would be requested — consolidated at PANL
from answer tokens (L22–28), routed to and held at CC (L30–36), and read out by the
unembedding matrix at the final layer. That cached representation is **not a log-probability
readout**: six log-prob summaries jointly explain ~10% of confidence variance while PANL adds
~38% unique variance beyond them, and the position that actually produces the answer (AC) is
causally inert for confidence. Verbal confidence is therefore a **second-order**,
computationally distinct self-evaluation of question–answer fit — the architectural
prerequisite for genuine error detection.

Two caveats the paper itself flags, and a faithful reproduction should too: cached retrieval
is the *dominant*, not the *sole*, pathway (partial recoveries/disruptions throughout suggest
overlapping mechanisms); and prompt wording was held fixed within each format — sensitivity to
paraphrase or persona framing ("respond uncertainly" vs. "confidently") was not tested.

---

## 5. Key numbers (quick reference)

| Quantity | Value |
|---|---|
| Gemma categorical accuracy / ECE / AUROC | 77.4% / 0.12 / 0.71 |
| Mean answer log-prob as correctness predictor (AUROC) | 0.75 |
| Steering peak layers, PANL / CC | L21–25 / L30–35 |
| Patching recovery at PANL (L25) / PANL+1 | 24.3% / −1.4% |
| Noising peak token-change, PANL / CC | ~14% (L25–26) / ~78% (L61) |
| Swap peak layer at PANL; L→H Δconfidence | L26; ≈ +0.21 |
| All 6 log-prob baselines combined → confidence R² | 0.100 |
| PANL (L40) unique R² beyond all baselines | 0.380 |
| AC decoding R² vs. PANL decoding R² | ≈0.2 vs. ≈0.75 |
| Attention blocking: CC→PANL peak change (minimal prompt) | ~21%, L30–36 |
| Attention blocking: PANL→answer peak change | ~20%, L22–28 (leads CC→PANL by 6–8 layers) |
| BigMath / MMLU accuracy (generalization) | 40.2% / 76.8% |
| Magistral: n after filtering / share "Almost certain" | 4,998 / 92% |
