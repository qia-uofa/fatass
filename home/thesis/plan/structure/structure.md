# Thesis Structure — *An Ontological Perspective on LLM Beliefs*

Goethe University Frankfurt, B.Sc. Informatik · Supervisor: Visvanathan Ramesh
Themenausgabe 27.06.2026 · Abgabetermin 31.08.2026

**Spine:** reproduce (Ch. 5) → generalize (Ch. 6–7) → argue ontologically (Ch. 8).
**Title note:** the officially issued title says *Beliefs*, not *Confidence* — the
title page must reproduce it verbatim, and the framing should follow: confidence
is one belief-like self-report among several, not the sole object.

---

## Front matter (regulatory, not optional)

- Title page with the issued title verbatim; paginated throughout (§35 PO 2019).
- **Zusammenfassung / Abstract** — required.
- **Erklärung zur Abschlussarbeit** bound into every copy + one loose copy.
- **Note on the Use of AI Tools** — what was AI-assisted (code implementation via
  `fatass`/Claude, brainstorming/planning) vs. what was not (RQs, interpretation,
  argument); git history + `./log` available on request.
  (← brainstorm `20260831-073832`: "Hilfsmittel" clause, no separate KI checkbox;
  substantial undisclosed AI use = Täuschung.)
- Open, unresolved: English-language approval (§35 Abs. 11, due at Anmeldung).

---

## 1. Introduction

- The two-signal observation: a model emits an answer *and*, separately, a verbal
  report about that answer — the internal state and the verbalization are computed
  at different places and times.
- The ontological question the gap raises: is a "belief" of an LLM a
  representational state it *has*, a linguistic act it *performs*, or an artifact
  of the observer's extraction method?
- Why confidence alone can't settle it — one construct gives one data point;
  a *family* of constructs is what discriminates the readings.
- Contributions, in order: (i) independent reproduction of Kumaran et al. 2026 at
  reduced scale; (ii) a generalized observation-method × ground-truth framework
  (`vonto`) extending the paper's method to six further self-report constructs and
  four datasets; (iii) an ontological reading of the resulting pattern, anchored on
  Benzon.
- Reading guide: which chapter answers which RQ.

## 2. Background

- **Two-phase elicitation protocol** — Phase 0 (front-loaded instruction block,
  prompt forced to end at `**Answer**:`), Phase 1 (answer re-inserted *as text*,
  forced `**Confidence**:` cue, next-token logits read at that position).
  (`vonto/calibration/generation.py`, `observation.py`; `archive/vconf/pipeline.py`)
- **Why the two phases are independent forward passes** — re-insertion as text,
  not a continued residual stream; this is what makes AC unreachable from Phase 1.
- **Token positions** — AC, PANL, PANL+1, FCC, CC (+ QTT, Trace k% in the
  reproduction). What each is and why PANL is the falsifying one.
  (`archive/vconf/positions.py`, `vonto/observation_method/positions.py`)
- **Reading a categorical self-report off logits** — 10-class Likert ladder,
  class midpoints, argmax over class-initial token ids; the tokenizer preconditions
  this rests on (pairwise-distinct class-initial tokens; PANL an isolated newline).
  (`vonto/observation_method/likert_om.py`, `positions.py`)
- **Intervention primitives** — residual-stream steering, patching, noising,
  representation swap, attention knockout; hook point = decoder-layer output.
  (`archive/vconf/hooks.py`, `attention.py`, `interventions.py`)
- **Metrics** — logit difference (target class fixed at the clean prediction),
  first-token change rate, recovery, Spearman ρ, ECE, AUROC.
  (`archive/vconf/metrics.py`; `vonto/calibration/calibration.py`)
- **Ontological vocabulary (define here, use in Ch. 8)** — Benzon's inheritance
  trees, paradigmatic vs. ontological transitions; representational state vs.
  linguistic performance vs. observer-relative artifact.
  (papers: Benzon 1985/87, 2023 — brainstorm `20260826-100257`)

## 3. Related Work

- **The anchor paper** — Kumaran et al. 2026, *How do LLMs Compute Verbal
  Confidence?* (ICML 2026, arXiv:2603.17839v3): confidence cached at
  answer-adjacent positions, retrieved at verbalization; explains more variance
  than log-probs alone.
- **Uncertainty quantification & calibration** — the literature the anchor builds
  on; verbalized confidence, semantic entropy, log-prob baselines.
- **Probing & self-verification of hidden states** — Zhang et al. 2025 (*Reasoning
  Models Know When They're Right*), Chen et al. 2026 (*Query-Level Uncertainty*),
  Li et al. 2026 (*Confidence Before Answering*), Huang et al. 2025 (*Confidence-
  Based Response Abstinence*). (all in `brainstorm/papers/`)
- **Ontology in knowledge representation** — Benzon 1985/87; *ChatGPT's
  Ontological Landscape* (2023); story-generation papers (2023/24) as secondary
  support on latent structure shaping surface output.
- **Epistemic emotions** (cognitive science) — justification for choosing
  knowledge-appraisal constructs (surprise/confusion/doubt family) over basic
  affect. (← brainstorm `20260827-083843`)
- **Gap statement** — nobody tests whether the cache-then-verbalize architecture
  is *specific to confidence*; that is exactly what Ch. 6–7 test.

## 4. Research Questions and Conceptual Framework

- RQ1 (ontological): what kind of entity is an LLM "belief"; what would count as
  evidence for each reading.
- RQ2 (reproduction): does the internal/verbal dissociation replicate at reduced
  scale, on a different model than the paper's primary one?
- RQ3 (generalization): does the same dissociation hold for other self-reportable
  epistemic constructs, or is confidence special?
- RQ4 (synthesis): what the RQ2+RQ3 pattern licenses — and what it does not.
- **The discriminating logic, stated explicitly**: generalization across constructs
  ⇒ a general cache-then-verbalize architecture (away from "confidence is a special
  introspective state"); failure to generalize ⇒ confidence is doing something
  distinctive. Either outcome is a result.
  (← brainstorm `20260827-043417`, the critical-feasibility session)
- **Deliberately bounded claim** — "more consistent with an information-caching /
  retrieval architecture than with naive introspective self-report", not a resolved
  metaphysics. (same session; repeated in Ch. 9)

## 5. Part I — Reproduction

*Method and results kept in one chapter: it is one codebase (`archive/vconf`), one
protocol, one validation table.*

- **5.1 Setup** — Qwen2.5-7B-Instruct, TriviaQA `rc.nocontext` validation, greedy
  decoding, bf16, GPT-4o-mini grading with alias-match fallback.
  (`archive/vconf/config.py`, `data.py`, `models.py`, `grading.py`)
- **5.2 Profiles and scale** — `paper` vs. `reduced`: every procedure, prompt,
  position, intervention and metric identical; only scale shrinks (1,000-trial
  behavioural run split 300 activation / 40 calibration / rest test).
  (`archive/README.md`, `vconf/notebook.py`)
- **5.3 The disjoint partition (§2.3.4)** — activation / calibration / test sets;
  why steering vectors must be extracted and tested on different questions.
- **5.4 Experiment battery** — one subsection each, with the paper's own expected
  value (`PAPER_TARGETS`) next to the obtained one:
  - behavioural baseline + hedging check (`exp0_behavioral.py`)
  - activation steering (`exp1_steering.py`)
  - activation patching (`exp2_patching.py`)
  - activation noising (`exp3_noising.py`)
  - representation swap (`exp4_swap.py`)
  - OOD control (`exp5_ood.py`)
  - probing / variance partitioning (`exp6_probing.py`)
  - answer-colon (AC) controls (`exp7_answer_colon.py`)
  - attention blocking (`exp8_attention_blocking.py`, `attention.py`)
  - generalization suite (`exp9_generalization.py`)
- **5.5 What reproduced** — cached retrieval at PANL, preceding CC, on Qwen
  categorical and numeric prompts. (`archive/diagnoses.md`, "What's solid")
- **5.6 What did not run, and why** — reported, not silently skipped:
  - `gemma-3-27b-it`: licence obtained, but ~54 GB needs multi-GPU sharding and
    `Gemma3TextModel.forward` computes rotary/mask tensors once on the initial
    device → garbage generations under `eager`, device-side assert under `sdpa`.
    A `transformers`/`accelerate` gap, not a code bug. (`diagnoses.md` addendum)
  - Big-Math / MMLU not provisioned (no repo id given by the guidebook).
  - Magistral checkpoint absent → reasoning-model axis implemented but unrun.
- **5.7 Self-audit of the reproduction** — the findings of `diagnoses.md` as a
  methodological result in its own right: Axis 3/4 wired up only partway,
  Exp. 6 missing six per-baseline R²_unique curves and the instruction-token
  probing position, `hash()`-seeded donor tie-breaking, no `eager` assertion
  before attention blocking. Reproducibility work that finds its own limits is
  worth reporting.
- **5.8 Non-obvious implementation decisions** — chat template with assistant
  prefill (so AC/CC really are the last prompt token); PANL-unisolable trials
  dropped rather than analysed; clean baselines recomputed with the same batching
  as the intervention runs (bf16 attention is not batch-invariant);
  `repetition_penalty=1.0` forced. (`archive/README.md`, "Choices the manual leaves open")

## 6. Part II — Method: Generalizing Beyond Confidence

*New package (`vonto`), built alongside rather than by renaming `vconf` — the
reproduction must stay runnable and verifiable. (← brainstorm `20260827-111955`)*

- **6.1 The decomposition** — a self-report construct splits into an
  **ObservationMethod** (what is elicited from the model) and a **GroundTruth**
  (what that report is checked against, as a `[0,1]` score, never a bare bool).
  (`vonto/observation_method/observation_method.py`, `ground_truth/ground_truth.py`)
- **6.2 Why this split is the load-bearing idea** — two independent levels:
  *mechanistic* (is there a causally manipulable internal representation of the
  class about to be verbalized) needs **no** ground truth and transfers to any
  scale; *validity/calibration* (does the report track anything real) is where
  ground truth is load-bearing. Confidence isn't privileged — it just happens to
  have correctness handed to it for free. (← brainstorm `20260827-111955`, the
  "are you saying confidence is meaningful only because of ground truth" exchange)
- **6.3 The construct inventory**
  | Self-report (OM) | Computed counterpart (GT) | Shared idea |
  |---|---|---|
  | `ConfidenceOM` | `CorrectnessGT` | is the answer actually right |
  | `CommitmentOM` | `ProbabilityGT` | how strongly the model committed to this exact sequence |
  | `NuanceOM` | `EntropyGT` | how many genuinely different answers were live |
  | `ChallengeOM` | `ChallengeGT` | resistance to adversarial evidence |
  | `VarietyOM` | `ListVarianceGT` | how spread out a generated list is |
  | `ImpurityOM` | `ImpurityGT` | how evenly a 20Q question splits the candidates |
  | — | `TemperatureGT` | **control column**: seed value the model never sees; must read ≈ 0 |
  - Shared 10-point `INTENSITY_LADDER` for every construct except confidence,
    whose class list is the paper's verbatim wording. (`likert_om.py`)
  - `tags`-based lookup (`vonto/tagged.py`) — `"general"` = applies to any
    single-answer trial; `variety`/`impurity` are dataset-exclusive.
- **6.4 Datasets, and their ontological motivation** (`vonto/dataset/`)
  - **TriviaQA** — the paper's own dataset; the anchor for comparability.
  - **Synonyms** — three human-annotated relation tiers, *twin* (interchangeable,
    EVALution/CogALexV, word2vec-filtered), *sibling* (co-hyponyms, K&H+N),
    *relative* (hyper/mero/attri/event, BLESS): a graded **ontological distance**
    in Benzon's inheritance-tree sense, not an arbitrary similarity axis.
  - **List elicitation** — "give me *k* things starting with X", `T` sampled
    temperatures per keyword; operationalizes the user's own observation of
    pattern-lock and category collapse in ChatGPT lists.
    (`brainstorm/papers/presentation.md`, "give me 20 things")
  - **Twenty questions** — games played out in full at generation time; the model's
    own next question is scored by the real Gini impurity of the split it induces.
    Operationalizes the abstract/concrete first-question hypothesis and its
    negative result. (`presentation.md`, "20 Questions")
  - **The shared keyword universe** — 10 WordNet noun synsets, 7 concrete / 3
    abstract, sampled by Brown-corpus frequency; every generated dataset draws
    from it, so a concreteness split is available everywhere.
    (`vonto/twenty_questions.py:CATEGORIES`)
- **6.5 Calibration experiment design** — the (dataset × OM × GT) cross-product,
  Spearman ρ per cell. (`vonto/calibration/calibration.py`, `3_heatmaps.ipynb`)
- **6.6 Steering experiment design** — extract `v = mean(H) − mean(L)` from
  self-report-ranked extraction trials, scale to 3 % of mean residual norm, inject
  at (layer, position), re-read the self-report. (`vonto/calibration/steering.py`,
  `4_steering.ipynb`)
  - **Controls are the point**: `POSITIONS = (PANL, PANL+1, FCC, CC)` — without a
    control, a flat PANL curve can't be distinguished from "the intervention
    mechanism does nothing."
  - Both directions always (`+α·v` and `−α·v`); disjoint extraction/test pools;
    balanced test selection (`select_balanced_test_trials`).
  - AC treated separately (`ac_steering_effect`): it lives in the Phase-0 prompt,
    so intervening there requires *regenerating the answer*, not one forward pass.
- **6.7 Methodological decisions, argued rather than defaulted**
  - `n_trials = 200`, not 999: SE(ρ) ≈ 0.032 at n=999 is already past where more
    trials change a conclusion, at ~5× the GPU cost; nothing batches, so cost is
    linear in `n_trials` and independent of dataset size.
    (← brainstorm `20260831-073832`)
  - **Relative** rank splits, never fixed thresholds: Qwen put 0 of 30 real
    synonyms trials in `CommitmentOM`'s bottom three classes — the paper's own
    absolute top-3/bottom-3 rule fails outright on that distribution.
    (`_filter_by_gt`, `select_balanced_test_trials`)
  - Always-regenerate over skip-if-cached: a stale cache silently matching a
    since-changed shape masked at least three real bugs (the Phase-0/Phase-1
    prompt fix, TriviaQA alias grading, the OM class-count standardization).
  - Undoing temperature scaling on `output_scores` so log-probs/entropies stay
    comparable across sampling temperatures. (`generation.py`)
  - Ranking extraction by the OM's *own* self-report, never by a paired GT —
    a ground truth plays no role in the paper's steering experiment.

## 7. Part II — Results

*Status as of writing: the reproduction's numbers exist; the extension's current-code
numbers are pending. State this plainly rather than presenting historical numbers as
current.*

- **7.1 Setup validation** — class-initial tokens pairwise distinct under Qwen's
  tokenizer for all six OMs (checked, not assumed); PANL isolation pass/fail rates
  per dataset; PQNL expected to fail on most natural questions (documented, not a bug).
- **7.2 Calibration heatmaps** — OM × GT Spearman ρ per dataset:
  - Exp. 1 baseline 3×3 (confidence/commitment/nuance × correctness/probability/
    entropy) over synonyms + TriviaQA
  - Exp. 2 full 4×4 adding challenge
  - Exp. 3 list elicitation: variety × {list-variance, temperature-control},
    plus the per-keyword within-keyword temperature-vs-variety breakdown
  - Exp. 4 twenty questions: impurity × impurity
- **7.3 Diagonal vs. off-diagonal** — does each construct's own computed
  counterpart beat the others? This is the "is the self-report about what it says
  it's about" test.
- **7.4 Steering sweeps** — per construct, all four positions × both directions ×
  layer, with SEM; the PANL-vs-PANL+1/FCC contrast is the read-out.
  Five pairs: confidence/TriviaQA, commitment/synonyms, nuance/synonyms,
  variety/list-elicitation, impurity/twenty-questions.
- **7.5 Cross-construct comparison** — the actual RQ3 answer: does the
  dissociation's *shape* (peak layer, position specificity, bidirectionality)
  look the same across constructs, or is confidence distinctive?
- **7.6 Concrete vs. abstract** — the 7/3 category split as a secondary axis
  wherever a generated dataset supplies it.
- **7.7 A note on superseded numbers** — the archived `phase_1` grid
  (`grid_summary.csv`: CC dominant at layer 22, PANL weak, PANL+1/FCC ≈ null) and
  the archived `phase_0` 9×6 matrices predate the current pipeline and the
  forced-completion-cue fix; reported as history, never as findings.
- **7.8 Negative and null results, kept** — the constant-`nan` self-report episode
  diagnosed as a prompt-mechanism bug rather than model behaviour; the temperature
  control column; a flat PANL curve *with* its controls is an interpretable result.

## 8. Discussion — The Ontological Argument

- What the reproduction alone establishes, and why it cannot answer RQ1 by itself
  (it reconfirms someone else's numbers).
- What the *generalization* buys: the cache-then-verbalize structure as a property
  of the architecture rather than of confidence-as-a-concept — or not.
- **Benzon applied, not merely cited**:
  - Inheritance trees / ontological vs. paradigmatic transitions read onto the
    synonyms tiers (twin → sibling → relative as movement through a category
    hierarchy) and onto the 20-questions partition (a question *is* an ontological
    cut over the candidate universe).
  - List collapse (pattern → category → supercategory) as a paradigmatic-to-
    ontological transition observable in surface output.
- **The three readings, adjudicated against the evidence**:
  representational state / linguistic performance / observer-relative artifact —
  which the data pressures, which it leaves open.
- **The observer-relativity problem, taken seriously**: every "belief" here is
  defined *by its extraction procedure* (a prompt, a cue, a position, an argmax).
  The `_filter_by_gt` / balanced-selection experience is evidence that the measured
  construct is partly an artifact of the measurement rule chosen.
- **Ground truth as an ontological commitment**: choosing `CorrectnessGT` vs.
  `ProbabilityGT` vs. `EntropyGT` for the *same* self-report is choosing what the
  belief is a belief *about*. (← brainstorm `20260827-111955`)
- Why "belief" is the right word for the generalized object and "confidence" was
  only ever one instance — reconciling the issued title with the anchor paper.

## 9. Limitations

- Single model (Qwen2.5-7B-Instruct); the paper's primary model was never
  executable here (Ch. 5.6) — no cross-architecture claim is available.
- Reduced scale throughout: `n_trials = 200`, small extraction/test pools; the
  reproduction's numbers are not the paper's numbers and never claim to be.
- The reproduction's own incompleteness (Ch. 5.7) bounds the "generalizes across
  datasets / reasoning models" claim to the two axes that actually ran.
- Self-report elicitation is prompt-shape dependent; PQNL failures, punctuation-
  merged PANL, forced-cue prefill are all measurement-design choices with effects.
- Ground truths of convenience: `ProbabilityGT` is length-dominated by
  construction; `ImpurityGT` scores the whole keyword universe, not the
  turn-accurate remaining set; `ChallengeGT` uses generated counterfeit evidence.
- The philosophical conclusion is an inference to the better-supported reading,
  not a settled metaphysics — restate the bounded claim from Ch. 4 here.
- AI-assisted implementation: scope disclosed in the front-matter note.

## 10. Conclusion and Future Work

- One paragraph per RQ, answered.
- The transferable artifact: OM × GT as a reusable frame for studying *any*
  verbalized self-report, not just confidence.
- Future work, concretely: Gemma once the `transformers`/`accelerate` sharding gap
  closes; the AC regeneration control and dual-α sweep still marked TODO in
  `4_steering.ipynb`; patching/noising/swap ported from `vconf` onto the `vonto`
  constructs; sentiment/emotion-labeled datasets (SST-2, GoEmotions) as
  ground-truth-bearing non-epistemic constructs.

---

## Appendices

- A. Prompt templates (Phase 0, Phase 1, challenge, partition) verbatim.
- B. Full class lists and midpoints per OM.
- C. Complete OM × GT matrices per dataset.
- D. Per-layer steering tables (all positions, both directions, SEM).
- E. Reproduction validation table: `PAPER_TARGETS` vs. obtained.
- F. Environment, checkpoints, and the exact config (`config.json`).

## Structural choice, flagged

Ch. 5 (reproduce) and Ch. 6–7 (extend) are **separate top-level chapters** rather
than shared Methodology/Results chapters split into subsections — justified here
because they are two different codebases (`vconf` vs. `vonto`), two different
protocols, and two different evidential roles. The alternative (one Methodology,
one Results, each split replicate/extend) is tighter on page budget; switch only if
the reproduction chapter turns out short. (← open item from brainstorm
`20260827-043417` / `20260827-083843`, resolved here in favour of separate chapters.)
