# Plain-Language Summary

## *How do LLMs Compute Verbal Confidence?*

This paper studies what happens **inside** a language model when you ask it "how confident
are you in your answer?" It doesn't just look at the confidence number the model outputs — it
opens up the model's internal activations to find out where and when that number actually
gets computed.

Two questions drive everything:

1. **When does the model figure out its confidence?** Does it only think about confidence at
   the moment you ask ("just-in-time"), or does it quietly compute and store a confidence
   signal right after answering, before it even knows you'll ask ("cached retrieval")?
2. **What is confidence actually based on?** Is it just a summary of how "sure" the model was
   while picking its answer tokens (i.e., basically just the token probabilities it already
   had) — or is it a separate judgment the model makes by re-evaluating whether the
   question and answer fit together?

**The paper's answer, in one sentence:** the model automatically computes and stores a
confidence signal right after it finishes answering (not only when asked), and that signal is
a genuinely separate judgment, not just a repackaging of how likely the answer tokens were.

---

## 2. Terms used below, explained plainly

- **Layer** — transformer models are stacked in ~30-60 processing steps ("layers"). Layer 1 is
  closest to the raw input tokens, the last layer is closest to the output.
- **Token position** — a spot in the sequence of words/pieces the model is reading, e.g. "the
  colon right after the word Answer" is one specific position.
- **Activation / residual stream** — at every layer and every position, the model keeps a big
  list of numbers that represents "what it currently knows/thinks" at that spot. Think of it
  as the model's internal notepad at that exact point in the text.
- **Logit** — a raw, pre-probability score the model assigns to each possible next word. Higher
  logit = model more inclined to output that word next.
- **Steering** — manually adding a specific direction (a vector) to the internal numbers at one
  spot, to nudge the model's output toward or away from something (here: higher or lower
  confidence).
- **Patching** — first sabotage the model's ability to know if the answer is right (see
  "corruption" below), then paste back the original, undamaged internal numbers at just one
  spot, and check whether that alone fixes the model's behavior.
- **Corruption** — deliberately erasing information the model would normally have (here: by
  replacing the answer text's internal representation with a generic "average answer") so its
  confidence output becomes unreliable, as a baseline to test recovery against.
- **Noising / mean-ablation** — replacing one spot's internal numbers with a generic average
  computed from many other examples, to see whether removing that spot's specific information
  breaks the model's confidence output.
- **Swap** — take the internal numbers from one example (the "donor") and drop them into a
  completely different example (the "recipient") at the same spot, to see whether specific
  information (not just generic disruption) transfers across.
- **Attention blocking** — models decide what to "pay attention to" at each step. This
  technique forcibly prevents one position from looking at another, to test whether info flows
  through that specific connection.
- **Probing** — training a small, simple classifier on the internal numbers at one spot to see
  if the information you care about (e.g., "will the answer turn out correct?") is present
  there at all, even if the model never actually uses it for its output.
- **AUROC** — a score from 0.5 (no better than a coin flip) to 1.0 (perfect) for how well a
  signal tells correct answers apart from wrong ones.
- **ECE (calibration error)** — how far the model's stated confidence is from how often it's
  actually right. Lower is better; 0 would be perfectly calibrated.

### The four key spots in the prompt (used in almost every experiment)

Picture the prompt as: `...question... **Answer**: <the model's answer> [NEWLINE] ...confidence
instructions... **Confidence**:`

- **AC ("answer-colon")** — the colon right *before* the model starts writing its answer. This
  is literally the spot that produces the answer's first word.
- **PANL ("post-answer newline")** — the newline immediately *after* the answer, before any
  confidence-related text has even appeared yet. This is the paper's prime suspect for "where
  confidence gets secretly saved."
- **PANL+1** — the very next token after PANL. Used as a control: if this spot behaves just
  like PANL, something's wrong with the experiment, because it shouldn't be special.
- **CC ("confidence-colon")** — the very last token of the whole prompt, right before the model
  states its confidence out loud. This is where confidence actually gets "spoken."

---

## 3. The experiments

### Experiment 0 — Does the model even give sensible confidence ratings?
**What they did:** Asked ~8,000 trivia questions, had the model answer, then had it rate its
own confidence (as a category like "Likely" or a number 0-100). Checked how well that
confidence matched actual correctness.
**Result:** The model is right about 77% of the time, and its stated confidence is a real
(if imperfect) signal of correctness. Interestingly, a simpler signal — how "smoothly" the
model generated the answer tokens (their raw probabilities) — predicts correctness even
*better* than the model's own stated confidence does. That's an early hint that the model
isn't just reading off token probabilities when asked for confidence.
**Point of this experiment:** Confirms there's something real worth investigating before
digging into how it's computed.

### Experiment 1 — Where in the network does "confidence" live?
**What they did:** Built a direction in the internal numbers that represents "high confidence"
vs "low confidence" (by averaging examples of each), then manually pushed the model's internal
numbers along that direction at different spots and layers, and watched whether its stated
confidence changed.
**Result:** Pushing at **PANL** (mid-network layers) changes the stated confidence.
Pushing at **CC** (later layers) changes it even more strongly. Pushing at the control spot,
**PANL+1**, does nothing — as expected.
**Point of this experiment:** Confirms confidence-related information already exists right
after the answer (PANL), before the model has even seen the confidence question — this rules
out "just-in-time" thinking.

### Experiment 2 — Is what's stored at PANL enough on its own to produce confidence?
**What they did:** Deliberately wiped out the model's ability to tell if its answer was
correct (by scrambling the internal representation of the answer text), then pasted back the
*undamaged* internal numbers at just one spot, to see if that alone restores normal confidence
behavior.
**Result:** Restoring **PANL** partially brings back correct confidence behavior. Restoring
**CC** brings it back almost completely, but only because CC is very close to the model's final
output stage anyway. Restoring the control spot, **PANL+1**, does nothing.
**Point of this experiment:** Shows PANL genuinely contains *enough* information on its own to
partially drive confidence — not just correlate with it.

### Experiment 3 — Is what's stored at PANL actually needed?
**What they did:** Wiped out just one spot's internal numbers (replaced with a bland average),
without otherwise damaging anything, and checked whether that alone breaks confidence.
**Result:** Wiping **PANL** partially breaks confidence output. Wiping **CC** breaks it more,
but mainly at very late layers (again, because CC is close to the output). Wiping **PANL+1**
changes nothing.
**Point of this experiment:** Confirms PANL isn't just sufficient (Exp. 2) — it's also
somewhat necessary. Together, Exp. 2 and 3 show PANL is a real, load-bearing part of how
confidence gets computed.

### Experiment 4 — Does PANL store "confidence" specifically, or just generic info about the answer?
**What they did:** Took the internal numbers from one example's PANL spot and transplanted
them into a *different, unrelated* example at the same spot — without changing that example's
actual question or answer text at all. Tried donor/recipient pairs with matching confidence
levels (as a control) and with opposite confidence levels (the real test).
**Result:** When a low-confidence donor's PANL numbers are transplanted into a
high-confidence recipient, the recipient's stated confidence goes down — and vice versa.
Transplants between examples with the *same* confidence level barely move anything.
**Point of this experiment:** The clearest proof that PANL specifically encodes a confidence
signal — not just some general "facts about this answer" — because the recipient's own
question and answer never changed, only the transplanted internal numbers did.

### Experiment 5 — Are these effects just artificial glitches from poking the model?
**What they did:** Checked whether all the pushing/wiping/transplanting in Experiments 1-4
pushes the internal numbers into a weird, unnatural range the model never normally visits.
**Result:** No — the changes made by every technique stay well within the range of variation
seen naturally across ordinary examples. And PANL and its "do-nothing" neighbor PANL+1 get
disturbed by about the same amount — yet only PANL actually changes the model's behavior.
**Point of this experiment:** Rules out "you just broke the model" as an explanation for
Experiments 1-4's results.

### Experiment 6 — Can you *detect* confidence info even without intervening, and is it just token probabilities in disguise?
**What they did:** Trained simple classifiers on the internal numbers at each spot to predict
(a) whether the answer is correct, and (b) how confident the model will say it is. Separately,
compared how much of the model's confidence rating can be explained by six different summaries
of the answer's token probabilities, versus how much *extra* the PANL internal numbers explain
on top of that.
**Result:** Confidence-related info can be read out of PANL earlier (in earlier layers) than
out of CC — matching the "computed early, used later" story. The six token-probability
summaries combined explain only about 10% of why the model rates one answer more confidently
than another. PANL's internal numbers explain nearly four times more than that, on top of the
probability summaries.
**Point of this experiment:** Strong evidence that verbal confidence isn't just a repackaging
of "how confident the model already was while writing the answer" (the token probabilities) —
it draws on something else entirely, which lives in PANL.

### Experiment 7 — Does the spot that generates the answer itself also drive confidence?
**What they did:** Repeated the pushing/wiping/detecting tests from Experiments 1-3-6, but at
**AC** — the exact spot that produces the model's first answer word — instead of PANL.
**Result:** None of it works. Pushing, wiping, and reading out confidence info at AC all fail,
about as badly as at the do-nothing control spot PANL+1.
**Point of this experiment:** Rules out the simplest possible explanation — that confidence is
just leftover signal from whatever machinery picked the answer. The spot that literally writes
the answer has essentially nothing to do with the confidence rating.

### Experiment 8 — How does the information actually travel, step by step?
**What they did:** Forcibly cut off specific "attention" connections (i.e. prevented one token
from looking at another) to trace the path information takes: does the final confidence spot
(CC) look directly at the question and answer, or does it instead look at PANL? And does PANL
itself look back at the answer text?
**Result:** Cutting CC's direct view of the question and answer barely matters. Cutting CC's
connection to PANL does matter — a lot. Cutting PANL's connection back to the answer tokens
also matters, and this break happens at *earlier* layers than the CC-to-PANL break.
**Point of this experiment:** Directly maps out the assembly line: **the answer feeds into
PANL, which then feeds into CC, which then gets converted into the words "Highly likely" (or
whatever) at the very end.**

### Experiment 9 — Does all of this hold up in other settings?
**What they did:** Reran the key experiments above with: a 0-100 numeric confidence scale
instead of categories; a completely different, smaller model (Qwen); two different kinds of
questions (math problems, multiple-choice trivia); and a "reasoning" model that writes out a
long chain of thought before answering.
**Result:** The same basic pattern holds everywhere — PANL matters, its do-nothing neighbor
doesn't, and PANL's information arrives before CC's. Some quirks show up and are explained
rather than treated as failures: e.g., when the model is almost always highly confident anyway
(as with multiple-choice questions and the reasoning model), the "push confidence up" transplant
works better than the "push confidence down" one, simply because there's more room to go up.
Also, for the reasoning model, wiping PANL alone doesn't break things much — because with a long
chain of thought, the same confidence-relevant information ends up copied into many places
along the trace, not just concentrated at PANL.
**Point of this experiment:** Shows this isn't a fluke of one prompt, one dataset, or one
model — it's a general strategy language models use.

---

## 4. The big picture

Right after a language model finishes answering a question — before anyone has even asked how
confident it is — it quietly computes a confidence judgment and tucks it away at one particular
spot in its internal state (right after the answer, at what this summary calls PANL). Later,
when actually asked to state its confidence, the model doesn't recompute that judgment from
scratch; it retrieves what it already stored and reports it.

That stored judgment is not simply "how likely were my answer words, on average" — it's a
separate evaluation of how well the question and the answer fit together, using signals beyond
raw token probabilities. This matters because a model that could *only* read off its own token
probabilities for confidence would never be able to say "wait, I don't think that's right" — a
second, independent judgment is exactly the kind of thing that would let a model notice its own
mistakes.

Two honest caveats: this "quietly precompute it" behavior is probably the main way models do
this, but not the *only* way — some of the interventions only partly worked, suggesting other,
overlapping mechanisms also contribute. And the researchers always used the same fixed wording
for their prompts; they didn't test whether rephrasing the question, or telling the model to
"sound uncertain," would change where or how this computation happens.
