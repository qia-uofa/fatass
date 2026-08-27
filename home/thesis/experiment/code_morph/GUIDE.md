# Guide: what this is and how to use it

This document assumes you have **not** read the paper this code reproduces. It explains
the idea in plain terms, the vocabulary you'll hit in the code and notebooks, how to
actually run things, and how to point the whole toolkit at a question other than
"confidence."

## 1. What question is this code answering?

Ask a language model a factual question. It answers. Now ask it: *"how confident are you
that answer is right?"* It'll happily give you a number or a phrase like "very likely."

The question this code investigates: **when the model produces that self-report, is it
reading off something it already figured out while it was writing the original answer —
or is it computing a fresh guess only because you happened to ask?**

Those two possibilities look identical from the outside (you get a confidence rating
either way), but they're different mechanistically:

- **"Just-in-time" computation** — the model has no notion of its own confidence until
  the moment it's asked. The confidence report is generated fresh, from scratch, at the
  point in the prompt where the question is posed.
- **"Cached retrieval"** — the model forms *some* internal signal about how sure it is
  while it's still writing the answer, before anyone has asked it to report anything.
  When later asked to self-report, it's just reading that signal back out.

The second option is the more interesting one: it would mean the model has an internal,
reusable notion of its own uncertainty, not just a party trick it performs on demand.
This codebase distinguishes the two by looking at *where in the token sequence* a usable
signal first appears, and whether you can *manipulate* that signal causally (not just
observe a correlation).

## 2. The experimental trick: two phases, one key position

Every trial runs in two steps:

1. **Phase 0.** Ask the question, let the model answer normally (greedy decoding). Record
   its answer.
2. **Phase 1.** Show the model back its own question-and-answer pair, and ask it to
   classify how confident it is, in one of ten bins ("No chance" ... "Almost certain").
   This is read with a *single forward pass* — no new text is generated; the model's
   next-token probabilities at the very end of the prompt directly give the confidence
   classification.

The trick is a token position called **PANL** — the newline that appears immediately
after the model's answer, *before* any confidence-related wording has even entered the
prompt. If the model has already formed an internal notion of its confidence by the time
it reaches PANL, some trace of that should be visible/manipulable at PANL's activations
— even though, textually, nothing at PANL has anything to do with confidence yet. Finding
a real effect there is evidence for cached retrieval; finding nothing is evidence for
just-in-time computation.

Contrast this with **CC** (the very last token of the prompt, right where the model is
about to type its confidence answer) — of course something confidence-related shows up
there, under *either* hypothesis. CC is not diagnostic on its own; PANL is.

## 3. Vocabulary you'll see everywhere

| Term | Plain meaning |
|---|---|
| **Trial** | One question, carried through Phase 0 and Phase 1. |
| **PANL** | "Post-answer newline" — the token right after the model's own answer, before any confidence wording. The key position. |
| **PANL+1** | The token right after PANL. Used as a *control*: if PANL shows an effect but PANL+1 (one token away) doesn't, that's evidence the effect is position-specific, not generic noise. |
| **CC** | "Confidence colon" — the very last token of the prompt, right where the self-report is generated. Effects here are expected under any hypothesis, so they don't distinguish anything by themselves. |
| **FCC** | The colon inside the *instructions* block (a second, earlier place the word "confidence" appears in the prompt). Another control position. |
| **AC** | "Answer colon" — in the Phase-0 prompt, the position right where the model is about to generate its *answer* (not its confidence). Used in Experiment 7 to check the self-report isn't just a byproduct of answer-generation machinery. |
| **QTT** | Third token of the question. A position that should show *nothing* — a sanity-check control. |
| **Class / class index** | One of the ten confidence bins ("No chance" → "Almost certain"), and its 0–9 index. |
| **Confidence (as a number)** | The midpoint of the predicted class's probability range, e.g. "Almost certain" → 0.95. |
| **Correctness** | Whether the model's Phase-0 answer was actually right, graded by GPT-4o-mini against reference answers. This is the *ground truth* the confidence report is checked against. |
| **ECE** | Expected Calibration Error — how far the model's stated confidence is from its actual accuracy. Low is good (well-calibrated). |
| **AUROC** | How well confidence *discriminates* correct from incorrect answers, regardless of calibration. |

## 4. The five ways of poking at the model (the "interventions")

Each of these answers a different flavor of the same question — does PANL causally
matter, and does it matter *before* CC does?

- **Steering** (Experiment 1) — nudge the residual stream at one position/layer in a
  "more confident" or "less confident" direction (computed as the difference between
  high- and low-confidence trials) and see if the reported confidence shifts.
- **Patching** (Experiment 2) — destroy the model's access to its own answer (by
  corrupting the answer tokens), then restore just *one* position's clean activations and
  see how much of the original confidence report comes back.
- **Noising** (Experiment 3) — replace one position's activation with the *average*
  activation across many trials (this disrupts, it doesn't push toward "neutral" — the
  average of "very confident" and "not confident" activations isn't "somewhat
  confident," any more than averaging "brilliant" and "terrible" gives you "mediocre").
- **Swap** (Experiment 4) — transplant one trial's PANL activation into a *completely
  unrelated* trial (different question, different answer) and see whether the borrowed
  confidence level comes along for the ride.
- **Attention blocking** (Experiment 8) — sever specific attention connections (e.g.
  "can CC even look at PANL?") and see what breaks. This is what actually establishes the
  causal *chain* — answer tokens → PANL → CC — rather than just "PANL matters" in
  isolation.

Two more experiments look at this without intervening at all:

- **Probing** (Experiment 6) — train a small classifier on frozen activations to see how
  *early* (which layer) confidence becomes linearly decodable, and whether that
  information is more than what you'd get from the model's raw token-probabilities alone.
- **Out-of-distribution control** (Experiment 5) — a sanity check that the interventions
  above aren't just breaking the model in a generic way (pushing activations somewhere
  weird) rather than specifically disrupting a confidence signal.

## 5. Running it

### Environment

Everything needs the environment `scripts/setup/_.sh` provisions (a conda prefix with
`torch`+CUDA, `pytest`, `jupyter`), and `~/.thesis-experiment.env` with `HF_TOKEN` (for
the gated Gemma 3 checkpoint) and `OPENAI_API_KEY` (for GPT-4o-mini grading — without it,
correctness falls back to cruder string matching, and every notebook tells you when
that's happening).

```bash
/scratch/qi/env/bin/python -m pytest tests -q     # unit tests, no GPU/API needed
```

### Notebooks

Run them **in order** the first time — Experiment 0 builds the question/answer/confidence
records every later notebook reads, and Experiment 1 builds the activation cache the
interventions and probes read from:

```bash
cd notebooks
/scratch/qi/env/bin/jupyter nbconvert --to notebook --execute --inplace \
    experiment_0_behavioral_baseline.ipynb
```

Two environment variables control scale:

- `VCONF_PROFILE=reduced` (default) or `paper` — `reduced` runs a smaller, faster model
  (Qwen) with fewer trials so everything finishes on one GPU; `paper` runs the full
  original setup (gated 27B Gemma checkpoint, thousands of trials). Either way, the
  *procedure* is identical — only the scale changes, and every notebook's first cell
  prints which one you're running and warns you when numbers won't match the paper's.
- `VCONF_MODEL=gemma|qwen|magistral` — which checkpoint, if you want to override the
  profile's default.

Each notebook prints a banner at the top (via `vconf.notebook.describe`) telling you the
model, the profile, the sentiment/ground-truth pair in use, and the trial counts — read
that first to know what you're looking at.

### Reading a notebook's output

Look for:

- **A comparison table against `PAPER_TARGETS`** — the paper's own reported numbers, so
  you can see at a glance whether your run is in the right ballpark (only meaningful
  under the confidence/correctness default — see §7).
- **A "layer curve" plot**, one line per position (PANL, PANL+1, CC, ...) — the x-axis is
  model layer, the y-axis is the effect size. The headline finding in most notebooks is:
  PANL shows a real effect (separates from its PANL+1 control), and PANL's effect peaks
  at an *earlier* layer than CC's. That ordering — PANL before CC — is the "cached
  retrieval" signature.
- **"Interpretation" markdown cells** at the end of each notebook, which spell out what a
  given result would mean and why.

## 6. Studying something other than confidence

This is the part specific to this fork of the code. The original codebase hardcoded two
things: *what the model self-reports* (confidence) and *what that report is checked
against* (whether the answer was factually correct). Both are now parameters.

- **`vconf.sentiment.SentimentSpec`** — defines what's being self-reported: a name, the
  ten-class vocabulary, and the phrasing used to ask for it.
- **`vconf.ground_truth`** — defines what the report is checked against: either
  `AliasCorrectness` (compare against a reference answer — the original setup) or
  `LLMCriterion("some yes/no question")` (judge the property directly from the response
  text — for anything that isn't "was this factually correct").

Example — studying whether a model's self-reported *toxicity* rating tracks whether the
response is actually judged toxic:

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
cfg = RunConfig(
    sentiment=toxicity,
    ground_truth=LLMCriterion("Is this answer toxic?"),
)
```

Pass `cfg` anywhere the notebooks pass a `RunConfig` (e.g. in place of
`nb.run_config("gemma-categorical")`), and every prompt, every intervention, every metric
in this codebase runs against *toxicity vs. is-it-toxic* instead of *confidence
vs. is-it-correct* — without changing a line of `vconf` code. The self-report prompt text
changes to match (`"Classify your toxicity into one of the following classes based on how
likely the answer above is to be perceived as toxic..."`); the mechanics (two-phase
protocol, PANL/CC positions, all five interventions, probing, metrics) stay exactly the
same.

You don't have to use `LLMCriterion` — if your new sentiment's ground truth is still
"was the underlying answer correct" (e.g. you want to ask the model how *difficult* it
found a question, still checked against whether it got the question right), just reuse
`AliasCorrectness()` and only swap the `SentimentSpec`.

## 7. What still only means something for confidence

Two things in this codebase are tied specifically to the paper's original confidence
study, and don't carry over automatically to a new sentiment:

- **`PAPER_TARGETS`, `PEAK_LAYERS` and every other hardcoded number** in the `exp*.py`
  modules are the *paper's own reported results for confidence*. If you run a different
  sentiment, there's nothing to validate against — you're exploring, not reproducing.
- **The hedging check** (`grading.hedging_rate`, run in Experiment 0) exists specifically
  to rule out the worry that "the confidence direction" secretly just encodes hedging
  words like "maybe" or "probably." It's a validity check for the confidence case; a
  different sentiment would need its own analogous sanity check if one is warranted, but
  none is assumed generically.

Everything else — the two-phase protocol, the position-finding machinery, the five
interventions, probing, and the metrics (ECE, AUROC, logit difference, recovery,
first-token change rate) — is genuinely generic and applies unchanged to whatever
`RunConfig(sentiment=..., ground_truth=...)` you build.
