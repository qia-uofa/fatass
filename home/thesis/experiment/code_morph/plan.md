# Morph plan: parameterize the sentiment and its ground truth

## What this morph does

The reproduction codebase in this directory (`vconf/`) implements one paper's
specific study: does a model's *self-reported confidence* reflect an internal
signal that exists before it's asked to report it, versus one computed only
at the moment of report? The self-report ("confidence", a 10-class Likert
scale) and the ground truth it's checked against ("correctness", graded by
GPT-4o-mini vs. TriviaQA/BigMath/MMLU gold answers) are both hardcoded.

This morph generalizes both into parameters: any verbally-reported property
("sentiment") checked against any ground truth becomes a `RunConfig(sentiment=
..., ground_truth=...)` away, with confidence/correctness preserved as the
default — a fully-validated instance of the general framework, not a special
case bolted on top of it.

## Why this is feasible without a rewrite

The pipeline already separates concerns that just happen to have one hardcoded
instance each:

- **Self-report mechanism** (prompt → forward pass → logits over K
  class-initial tokens → argmax → midpoint) is pure plumbing; nothing about it
  depends on which trait the classes name.
- **Ground truth mechanism** is already an LLM-judge pattern (`grading.py`:
  system prompt + yes/no question). Generalizing "is this answer correct
  against these gold aliases" to "is property X true of this response" is the
  same call shape with a different question string.
- **Intervention machinery** (`hooks.py`, `attention.py`, `activations.py`,
  `interventions.py`) operates on token positions and activations only —
  already sentiment-agnostic, parameterized by position names and the two
  extreme classes.
- **`metrics.py`** (ECE, AUROC, logit-diff, recovery) takes bare arrays —
  already generic; `confidence()`/`confidence_change()` already accept an
  optional `midpoints` override.

So the real work is lifting two things from module-level constants into data
objects threaded through `RunConfig`, not restructuring the pipeline.

## Architecture

### `vconf/sentiment.py` (new)

```python
@dataclass(frozen=True)
class SentimentSpec:
    name: str
    classes: tuple[str, ...]                    # ordered low -> high
    class_ranges: dict[str, tuple[float, float]]
    high_band: tuple[str, ...]
    low_band: tuple[str, ...]
    highest_class: str                          # steering-vector pole
    lowest_class: str                            # steering-vector pole
    # prompt template fragments, parameterized by trait wording
    ...

CONFIDENCE = SentimentSpec(...)   # reproduces today's CLASSES/CLASS_RANGES/
                                   # instructions character-for-character
```

`prompts.py`'s builder functions (`build_confidence_prompt`,
`build_phase0_prompt`, `build_magistral_confidence_prompt`) gain a
`sentiment: SentimentSpec = CONFIDENCE` parameter and build instructions from
it instead of module-level `CLASSES`/`CLASS_RANGES`/`_CLASS_LIST`.

### `vconf/ground_truth.py` (new)

```python
class GroundTruth(Protocol):
    def label(self, item: QuestionItem, trial: Trial) -> bool: ...

class AliasCorrectness(GroundTruth):
    # wraps today's grading.py behavior unchanged: GPT-4o-mini vs gold
    # aliases, falling back to alias_match_grader without an API key.
    ...

class LLMCriterion(GroundTruth):
    # generic: ask GPT-4o-mini a supplied yes/no question about
    # (item, trial.answer). The question string IS the parameter — no new
    # code needed per ground truth.
    def __init__(self, question: str): ...
```

`grading.py` stays as-is (the low-level grader functions);
`ground_truth.py` composes them. Ground truth stays **boolean-only** — ECE
and AUROC are calibration-against-a-binary-event metrics; generalizing them
to continuous ground truth is a bigger, separate change and out of scope
unless asked for.

### `config.py`

`RunConfig` gains:

```python
sentiment: SentimentSpec = CONFIDENCE
ground_truth: GroundTruth = field(default_factory=AliasCorrectness)
```

Every existing `preset(...)` branch is unchanged (defaults cover them).
Composing a new axis is just `RunConfig(sentiment=MySpec, ground_truth=
LLMCriterion("..."), ...)` — no registry, no config file, no auto-discovery.

## Backward compatibility: the notebooks must not need to change

Checked every notebook and every `exp*.py`/`metrics.py`/`plotting.py`/
`notebook.py` for what they actually touch. Real coupling found:

- All 10 notebooks and `exp1`/`exp2`/`exp3`/`exp4`/`exp9`/`plotting.py`
  import `prompts.CLASSES` and/or `bands`/`HIGH_BAND`/`LOW_BAND`/
  `HIGHEST_CLASS`/`LOWEST_CLASS` as **module-level names**.
- `exp0`/`exp1`/`exp6`/`pipeline.py`/`notebook.py` read/write `trial.correct`
  as an attribute, by that name.
- `nb.graded()`, `nb.run_config()`, `E0.calibration()`,
  `E0.class_distribution()` etc. are called from notebooks with their
  *current* signatures — no `sentiment`/`ground_truth` argument anywhere.

Rules to keep all 10 notebooks running unmodified, byte-identical output:

1. **Don't rename `Trial.correct`.** It's already a generic boolean; keep
   the name, document it as "the ground-truth label, meaning defined by
   `cfg.ground_truth`."
2. **Keep `prompts.CLASSES`, `CLASS_MIDPOINT`, `HIGH_BAND`, `LOW_BAND`,
   `HIGHEST_CLASS`, `LOWEST_CLASS`, `QWEN_HIGH_BAND`/`QWEN_LOW_BAND`,
   `bands()` as real module-level names**, defined from `CONFIDENCE`
   (e.g. `CLASSES = CONFIDENCE.classes`) — not deleted in favor of
   `cfg.sentiment.classes` everywhere.
3. **Every new parameter is optional, defaulting to today's exact
   behavior**: `nb.graded(trials, ground_truth=None)`,
   `E0.class_distribution(trials, classes=None)`, etc. fall back to
   `CONFIDENCE`/`AliasCorrectness()` when omitted — exactly how every
   existing notebook calls them.
4. Internals that currently read the module constant directly
   (`pipeline.py`'s `P.CLASS_MIDPOINT[cls]`, the `exp*.py` grading calls)
   switch to reading `cfg.sentiment`/`cfg.ground_truth` — invisible to
   notebooks since none of them construct a non-default `RunConfig`.

## Files touched

| File | Change |
|---|---|
| `vconf/sentiment.py` | new: `SentimentSpec`, `CONFIDENCE` instance |
| `vconf/ground_truth.py` | new: `GroundTruth`, `AliasCorrectness`, `LLMCriterion` |
| `vconf/prompts.py` | builders take `sentiment` param (defaulted); module constants kept as `CONFIDENCE.*` re-exports |
| `vconf/config.py` | `RunConfig.sentiment`/`.ground_truth` fields (defaulted) |
| `vconf/grading.py` | unchanged |
| `vconf/pipeline.py` | internal reads switch to `cfg.sentiment`/`cfg.ground_truth`; `Trial.correct` field name unchanged |
| `vconf/metrics.py` | unchanged (already generic; default `MIDPOINTS` still derives from `CONFIDENCE`) |
| `vconf/exp0…exp9.py` | grading calls go through `cfg.ground_truth`; new params default to today's behavior |
| `vconf/results.py`, `plotting.py` | thread `cfg.sentiment` where currently importing `CLASSES` directly, with defaults preserved |
| `vconf/notebook.py` | `nb.graded(..., ground_truth=None)`; `nb.describe()` gains one banner line naming the active sentiment/ground truth |
| `tests/` | new unit tests for `SentimentSpec`/`GroundTruth` construction and prompt-building with synthetic data, no GPU/API needed |
| `README.md` | document the parameterization |

**Explicitly not doing:** no plugin registry or auto-discovery, no
env-var-driven sentiment selection, no continuous (non-boolean) ground truth,
no hardcoded second example sentiment wired into any preset/notebook/test —
genericity is proven by the interface accepting arbitrary instances, not by
running a second one.

## Notebook narrative changes

The notebooks' prose isn't just confidence-flavored vocabulary — it argues a
specific hypothesis ("just-in-time computation" vs. "cached retrieval") through
PANL/CC timing. Split:

- **Generalizes, gets reworded:** the mechanistic argument itself — "if the
  reported {sentiment} reflects a pre-existing internal signal rather than
  something computed only when asked, that signal must be steerable/
  patchable/decodable at the pre-answer position, not just at the moment of
  report." This logic doesn't depend on the trait being confidence.
- **Doesn't generalize, stays concrete and labeled:** validation tables,
  specific numbers (ECE=0.12, AUROC=0.71, peak layers 21–25/30–35), and the
  hedging-language check (which specifically rules out "confidence direction
  = hedging words"). These are the paper's findings about confidence, not
  guarantees of the framework — rewriting them as generic would misrepresent
  them.
- **Experiment 0's opening markdown** gets one new paragraph stating the
  general framework explicitly: the two-phase protocol + intervention
  battery studies any `(sentiment, ground_truth)` pair via `RunConfig`; these
  ten notebooks run its fully-validated instance (confidence vs. TriviaQA
  correctness), matching the original paper.
- **`nb.describe(cfg)`** gains one printed line naming the active
  sentiment/ground truth at runtime, so the parameterization is visible in
  the executed output, not just asserted in prose above it.
- Not doing: templating markdown headers off `cfg.sentiment.name` (e.g. so
  the title itself rewrites per sentiment) — needs notebook-generation
  tooling (papermill or similar) that doesn't exist here; new infrastructure
  for a cosmetic win nobody asked for.

## Validation

None will be executed as part of this morph (GPU/API cost; code has already
been reviewed manually). No pytest run, no notebook execution. Correctness is
established by code review and by the backward-compatibility argument above
(every new parameter defaults to reproducing current behavior exactly).
