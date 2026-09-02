# Reproduction code — *How do LLMs Compute Verbal Confidence?*

Implements the reproduction guidebook (`docs/manual/reproduction-guidebook.md`, with its
condensed requirements spec in `docs/manual/spec.md` — Kumaran et al., ICML 2026 /
arXiv:2603.17839v3): the shared setup of §2 and all ten experiments (§3–§12), as a reusable
Python package, one notebook per experiment, and a `pytest` suite.

```
code/
├── vconf/                     the reusable module
│   ├── config.py              checkpoints, layer sweeps, trial counts, §13 defaults, paths
│   ├── sentiment.py           SentimentSpec — what verbally-reported property is elicited
│   ├── ground_truth.py        GroundTruth — what that report is checked against
│   ├── prompts.py             the §2.5 templates verbatim + the class/midpoint table
│   ├── data.py                TriviaQA / Big-Math / MMLU loading, dedup, the §2.3.4 partition
│   ├── models.py              loading on CUDA, chat templating, class-initial tokens, checks
│   ├── positions.py           AC / first A / last A / PANL / PANL+1 / FCC / CC / QTT / Trace k%
│   ├── pipeline.py            the §2.4 two-phase protocol (Phase 0 → Phase 1)
│   ├── grading.py             GPT-4o-mini grading + hedging check, cached to disk
│   ├── hooks.py               residual-stream interventions and embedding corruption (§2.10)
│   ├── attention.py           attention knockout: windows, pathways, masks (§11)
│   ├── activations.py         activation collection and the on-disk store
│   ├── interventions.py       the shared runner + the §2.8 metric bundle
│   ├── metrics.py             logit difference, confidence, change rate, recovery, ECE, AUROC
│   ├── results.py             per-trial frames, mean ± SEM, peak layers, paired tests
│   ├── plotting.py            layer curves, reliability diagrams, comparison tables
│   ├── notebook.py            run profiles and the cached trial/activation sets
│   └── exp0_behavioral.py … exp9_generalization.py    one module per experiment
├── notebooks/                 one notebook per experiment section, named after it
└── tests/                     pytest suite over the module (no model or dataset needed)
```

## Beyond confidence: a general sentiment / ground-truth pipeline

The manual studies one verbally-reported property (confidence) checked against one ground
truth (answer correctness). Nothing about the two-phase protocol, the intervention battery
(steering / patching / noising / swap / attention blocking) or the metrics actually depends on
that choice — they only ever read a ten-class Likert scale and a boolean label through two
parameters on `RunConfig`:

```python
from vconf.config import RunConfig
from vconf.sentiment import SentimentSpec
from vconf.ground_truth import LLMCriterion

toxicity = SentimentSpec(
    name="toxicity",
    criterion="how likely the answer above is to be perceived as toxic",
    probability_clause="the answer is toxic",
    classes=("Not at all", "Somewhat", "Very"),
    class_ranges={"Not at all": (0.0, 0.33), "Somewhat": (0.33, 0.67), "Very": (0.67, 1.0)},
    high_band=("Very",), low_band=("Not at all",),
    highest_class="Very", lowest_class="Not at all",
)
cfg = RunConfig(sentiment=toxicity, ground_truth=LLMCriterion("Is this answer toxic?"))
```

- **`SentimentSpec`** (`sentiment.py`) is what's elicited: the class vocabulary and the prompt
  wording ("classify your `{name}` into one of the following classes based on `{criterion}`").
  `CONFIDENCE` is the manual's own instance, reproduced character-for-character — every
  builder in `prompts.py` returns that exact literal text for it, so its tokenization (and
  every `PAPER_TARGETS` number in this repo) is unaffected by this parameterization.
- **`GroundTruth`** (`ground_truth.py`) is what the report is checked against: `AliasCorrectness`
  wraps the manual's own grading (§2.3.1) unchanged; `LLMCriterion(question)` is the general
  case — any property judged from the response text alone is just a yes/no question string, not
  new code.

Both default to the manual's instance (`CONFIDENCE`, `AliasCorrectness()`), so every existing
preset, module and notebook in this repo is unaffected unless a `RunConfig` explicitly asks for
something else. One deliberate simplification: the structural prompt markers a trial is parsed
against (`**Confidence**:`, `**Answer**:`) stay fixed for every sentiment — they mark *where*
the self-report token sits, which the position-finding and intervention machinery depends on;
*what the self-report means* is what actually varies, and that's carried entirely by the
instruction prose, not the marker text. Ground truth stays boolean-only, since ECE and AUROC
are both calibration-against-a-binary-event metrics.

## Running

The environment is the one `scripts/setup/_.sh` provisions: the conda prefix at
`/scratch/qi/env`, `$PROJECT_ROOT=/scratch/qi/project`, and the TriviaQA `rc.nocontext`
validation split saved under `data/raw/triviaqa`.

```bash
/scratch/qi/env/bin/python -m pytest tests -q                       # unit tests
cd notebooks && /scratch/qi/env/bin/jupyter nbconvert --to notebook \
    --execute --inplace experiment_0_behavioral_baseline.ipynb      # one experiment
```

Run the notebooks in order the first time: Experiment 0 builds the Phase-0/Phase-1 trial set
that the rest read from `$PROJECT_ROOT/results/trials`, and Experiment 1 builds the activation
store under `$PROJECT_ROOT/activations`. Figures are written to `$PROJECT_ROOT/results/figures`.

Everything runs on the GPU: `vconf.models.load_model` places the checkpoint on
`torch.device("cuda")` and raises if CUDA is unavailable; hooks, interventions and attention
masks all operate on device tensors. Only the probes (scikit-learn) and the metric functions
run on CPU, which the manual's §9 prescribes.

### Run profiles

Two environment variables select what a notebook runs:

| Variable | Values | Meaning |
|---|---|---|
| `VCONF_PROFILE` | `reduced` (default), `paper` | which scale to run |
| `VCONF_MODEL` | `gemma`, `qwen`, `magistral` | which checkpoint |

`VCONF_PROFILE=paper` is the manual's own setting: `google/gemma-3-27b-it`, the 22-layer
sweep of §2.9, 7,858 behavioural questions, 3,000 activation trials, 200/400-trial test sets.
It needs the Gemma 3 licence accepted and `HF_TOKEN` set in `~/.thesis-experiment.env`.

`reduced` (the default, and what the committed notebook outputs were produced with) keeps
every procedure, prompt, position, intervention and metric **identical** and shrinks only the
scale: `Qwen/Qwen2.5-7B-Instruct` (itself the manual's Axis-2 model, §12.2), a 6-layer subset
of that model's sweep, 300 activation trials, 24–32-trial test sets. Its numbers are *not*
reproductions of the paper's numbers, and every notebook says so in its banner.

### The disjoint partition (§2.3.4)

Every notebook runs one behavioural pass and then splits it: `nb.split_activation_holdout`
takes the activation-collection set off the front (steering vectors, probes, the natural
pairwise variability), and the balanced calibration set (patching corruption and noising
means) plus the per-experiment test trials are drawn from the holdout that remains. So
steering vectors are extracted on one set of questions and tested on another, as §2.3.4 and
§4.2 require, and the calibration set stays disjoint from the test sets. Under the reduced
profile the behavioural run is 1,000 trials, split 300 activation / 40 calibration / the rest
test; under the paper profile it is 7,858, split 3,000 / 100 / the rest.

## Where each manual section lives

| Manual | Module | Notebook |
|---|---|---|
| §2.1–2.3 environment, models, datasets | `config.py`, `models.py`, `data.py` | — |
| §2.4 two-phase protocol | `pipeline.py` | all |
| §2.5 prompts | `prompts.py` | all |
| §2.6 token positions | `positions.py` | all |
| §2.7 trial pools | `exp1…exp4` selectors | all |
| §2.8 metrics | `metrics.py`, `interventions.py` | all |
| §2.9 layer sweep | `config.LAYER_SWEEPS` | all |
| §2.10 hooks | `hooks.py`, `activations.py` | all |
| §3 behavioural baseline | `exp0_behavioral.py` | `experiment_0_behavioral_baseline` |
| §4 steering | `exp1_steering.py` | `experiment_1_activation_steering` |
| §5 patching | `exp2_patching.py` | `experiment_2_activation_patching` |
| §6 noising | `exp3_noising.py` | `experiment_3_activation_noising` |
| §7 swap | `exp4_swap.py` | `experiment_4_activation_swap` |
| §8 OOD control | `exp5_ood.py` | `experiment_5_ood_control` |
| §9 probing / variance partitioning | `exp6_probing.py` | `experiment_6_probing_variance_partitioning` |
| §10 answer-colon controls | `exp7_answer_colon.py` | `experiment_7_answer_colon_controls` |
| §11 attention blocking | `attention.py`, `exp8_attention_blocking.py` | `experiment_8_attention_blocking` |
| §12 generalization suite | `exp9_generalization.py` | `experiment_9_generalization_suite` |
| §14 validation table | `PAPER_TARGETS` in each `exp*` module | the validation cells |

Each experiment module carries the manual's expected values as a `PAPER_TARGETS` (and, where
applicable, `PEAK_LAYERS`) constant, so every notebook can print its results next to the
paper's.

## Choices the manual leaves open

§13's fifteen underdetermined details are implemented at the manual's recommended defaults
(`config.py`: `RIDGE_ALPHA`, `LOGREG_C`, `ECE_BINS`, `OOD_PAIRS`, `DONOR_QUANTILE_BINS`,
`TRIVIAQA_SPLIT`/`TRIVIAQA_CONFIG`, `MMLU_SPLIT`, the 3%-of-residual-norm steering scale, the
decoder-layer-output hook point, the §13 #12 Phase-0 wording). Beyond those, four decisions had
to be made to make the code run at all; each is marked in the source:

1. **Chat template with an assistant prefill** (§13 #2 leaves the choice open but demands
   consistency). The prompt body is a single user turn and the trailing cue —
   `**Confidence**:` in Phase 1, `**Answer**:` in Phase 0 — is prefilled as the start of the
   assistant turn, so CC (respectively AC) really is *the very last token of the prompt*, as
   §2.6 requires, and the next-token logits are read there.
   *Exception:* the minimal numeric prompt (§2.5.3) is fed as raw text, because that prompt
   exists precisely to minimise the template tokens between PANL and CC, and a chat template
   would reinsert turn markers there and put the PANL+1 control on a special token.
2. **Phase 0 for the minimal numeric prompt.** §13 #12 defines the Phase-0 prompt by moving a
   prompt's confidence-instruction block to the start, but the minimal prompt has no
   instruction block — only a cue. Phase 0 for that run therefore uses the canonical
   categorical Phase-0 prompt (`prompts.PHASE0_KIND`), which also yields the Phase-0
   confidence class the protocol records.
3. **Trials whose PANL is not isolable are filtered out**, rather than analysed. §2.6 requires
   the post-answer newline to be a single unmerged token and §14.3 lists a merged newline as
   the cause of a spurious PANL/PANL+1 dissociation. A PANL token is accepted when it starts
   exactly at the post-answer newline and contains only whitespace — so a tokenizer that merges
   the numeric prompt's blank line into one `"\n\n"` token is fine, while an answer ending in
   punctuation that merges into `".\n"` is not, and that trial is dropped.
4. **Clean baselines are recomputed with the same batching as the intervention runs**
   (`interventions.compute_clean_logits`). bf16 attention is not bit-exact across batch
   compositions, and the §2.8 metrics compare an intervened run against its clean baseline
   token by token, so reusing a differently batched baseline would manufacture first-token
   changes. Greedy generation also passes `repetition_penalty=1.0` explicitly, since a
   checkpoint's own `generation_config` may otherwise penalise the digits that appear in the
   numeric prompts.

## What cannot run on this machine, and why

These are reported by the code, not silently skipped:

* **`google/gemma-3-27b-it` is a gated repository** and `HF_TOKEN` is empty in
  `~/.thesis-experiment.env`, so the primary model of every main-text experiment cannot be
  downloaded here. The `paper` profile targets it unchanged; the default profile runs the
  manual's Axis-2 model instead.
* **No `OPENAI_API_KEY`**, so the GPT-4o-mini grader of §2.3.1 and the hedging check of §3.2
  fall back to normalised alias matching and a keyword check. `grading.gpt4o_mini_grader` and
  `grading.gpt4o_mini_hedging_check` implement the manual's version and are used automatically
  as soon as a key is present; every notebook prints which grader produced its labels.
  Alias matching is stricter than an LLM grader on TriviaQA, so accuracy (and hence ECE) from
  the fallback is pessimistic.
* **Big-Math and MMLU are not provisioned.** The manual names no Hugging Face repo id or
  configuration for either, and `scripts/setup/_.sh` deliberately left their downloads
  unspecified rather than guessing. `data.load_bigmath` / `data.load_mmlu` read whatever has
  been saved into `$PROJECT_ROOT/data/raw/{bigmath,mmlu}` and otherwise raise
  `DatasetNotProvisioned` naming that reason; Experiment 9's Axis 3 reports it and prints the
  accuracy anchors to match (40.2% / 76.8%).
* **`mistralai/Magistral-Small-2506` is not in the local cache.** Axis 4's code path is fully
  implemented (`exp9_generalization`: CoT Phase 0, the trace-carrying Phase-2 prompt, the
  stratified activation set, the response-block corruption scope, trace-length donor matching
  and the ten `Trace k%` probe positions) and runs as soon as the checkpoint is downloaded.

One environment repair was needed on top of `setup/_.sh`: the `torch>=2.3` it installs
resolved to a CUDA 13 build, which cannot see this machine's driver (12.6), so
`torch==2.10.0+cu126` was installed into the same conda prefix. `pytest`, `jupyter` and
`nbconvert` were installed there too, since the setup script does not include them.
