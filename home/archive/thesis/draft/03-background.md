# 2. Background

This chapter defines everything the later chapters use without further comment:
the elicitation protocol, the token positions it creates, how a categorical
self-report is read off logits, the intervention primitives, the metrics, and
the philosophical vocabulary applied in Chapter 8. All acronyms are spelled out
on first use.

## 2.1 The two-phase elicitation protocol

Both the reproduction and the extension elicit a self-report in two stages.

**Phase 0 (answer generation).** The model receives the classification
instructions front-loaded at the start of the prompt, followed by the question,
and the prompt is forced to end at the literal cue `**Answer**:`. The model's
own continuation from that point is decoded greedily and recorded as the
answer, together with the per-token log-probability and the full-distribution
Shannon entropy at each answer step. Recording both during generation means no
later stage needs an extra forward pass to grade the answer's probability or
entropy.

**Phase 1 (self-report elicitation).** A fresh prompt is built in which the
model's own answer from Phase 0 is re-inserted as text, in a
`Question: …\n**Answer**: …` block, followed by the classification
instructions. The prompt is again forced to end at a cue, this time
`**Confidence**:` (or the analogous cue for whichever construct is being
elicited). One forward pass is run and the next-token logits are read at that
forced position.

The two phases are independent forward passes. Phase 1 does not continue Phase
0's residual stream; it re-encodes the answer as ordinary text. This is what
makes each phase separately cacheable, and it is also what makes the
answer-colon position (§2.2) unreachable from Phase 1, a fact §5.4.8 and §6.6
both depend on. Because the transformer's forward pass is a function of the
preceding tokens only, supplying the answer as context produces the same
representation at the post-answer position that autoregressive generation would
have produced there (Kumaran et al., 2026).

## 2.2 Token positions

The protocol creates a small set of named positions, and nearly every result in
this thesis is a claim about one of them.

- **AC** (answer colon): the last token of the Phase-0 prompt. Its final-layer
  residual stream is what the unembedding matrix turns into the first answer
  token's logits, so it is causally implicated in producing the answer.
- **PANL** (post-answer newline): the newline immediately after the answer in
  the Phase-1 prompt. This is the falsifying position. Causal attention prevents
  it from attending to anything later in the prompt, so at PANL the model cannot
  yet "know" that a rating will be requested. If steering there changes the
  reported class, no account on which the report is computed on demand survives.
- **PANL+1**: the token immediately after PANL. It is the mandatory control. It
  is one token away from PANL and subject to the same interventions, so an
  effect at PANL that also appears at PANL+1 is generic disruption rather than a
  confidence-specific effect.
- **FCC** (first confidence colon): the colon inside the instruction block's own
  format example, `**Confidence**: $CLASS`. A second control, further away and
  inside instruction text rather than content.
- **CC** (confidence colon): the final token of the Phase-1 prompt, where every
  class read is taken. This is the verbalization site.
- **QTT** (third question token) and **Trace k%** (evenly spaced positions
  across a reasoning trace) appear only in the reproduction's probing and
  reasoning-model experiments.

Formally, writing $h^{(\ell)}_p(x)$ for the residual-stream activation at token
position $p$ on the output of decoder layer $\ell$ for token sequence $x$, and
$z(x)$ for the next-token logits at the last position,

$$
h^{(\ell)}_{p}(x) \in \mathbb{R}^{d}, \qquad \ell \in \{0,\dots,L-1\},\ p \in \{0,\dots,|x|-1\}
\tag{P1}
$$

every intervention in this thesis writes to some $h^{(\ell)}_p$ and every read
is taken from $z$ at CC. The hook point is the decoder layer's output, which is
what a `forward_hook` on the layer module observes.

## 2.3 Reading a categorical self-report off logits

The self-report is categorical: ten ordered classes, from `"No chance"` to
`"Almost certain"` in the confidence case. Rather than generating the class name
and parsing it, a single forward pass is run and the logits at the ten
class-initial token ids are compared. Writing $C^\omega = (c^\omega_1, \dots,
c^\omega_K)$ for the class list of construct $\omega$ ordered low to high, with
$K = 10$, the class-initial token ids and the read are

$$
\iota^{\omega}_{k} \;=\; \mathrm{TOK}\bigl(\texttt{" "} \oplus c^{\omega}_{k}\bigr)_{1},
\qquad
\hat{y}_{\omega}(\theta) \;=\; \operatorname*{argmax}_{k \in \{1,\dots,K\}} z^{\omega}(\theta)_{k},
\qquad
m_{\omega}(\theta) \;=\; m^{\omega}_{\hat{y}_{\omega}(\theta)} .
\tag{36--38}
$$

Two preconditions make this valid, and both are properties of the tokenizer
rather than of the class names, so both are verified per model rather than
assumed. First, the class-initial tokens must be pairwise distinct,

$$
\iota^{\omega}_{k} \neq \iota^{\omega}_{k'} \quad \text{for all } k \neq k' ,
\tag{37}
$$

or the argmax cannot tell two classes apart. The paper's own class wording was
modified from Yoon et al. (2025) precisely to satisfy this. Second, PANL must be
its own isolated whitespace token; if the answer ends in punctuation the
tokenizer merges the trailing character and the newline into a single `".\n"`
token, and the position semantics of every PANL result collapse.

The scalar $m_\omega(\theta)$ is the class midpoint. The unit interval is
divided evenly across $K$ classes,

$$
m^{\omega}_{k} \;=\; \frac{k - \tfrac{1}{2}}{K},
\qquad k = 1,\dots,K,
\tag{31}
$$

which for $K = 10$ reproduces the paper's canonical midpoints
$0.05, 0.15, \dots, 0.95$ exactly. Every comparison between a self-report and a
computed quantity is a comparison of $m_\omega$ against that quantity.

## 2.4 Intervention primitives

Five causal interventions are used, all operating on residual-stream
activations at a single (layer, position) unless stated otherwise.

**Steering** adds a direction to the residual stream. The direction is built by
contrasting the mean activation of high-reporting trials against the mean of
low-reporting trials, normalized to a fixed fraction of the residual norm, and
injected at test time in both signs.

**Patching** follows a corrupt-then-restore paradigm (Meng et al., 2022;
Heimersheim & Nanda, 2024). Answer-token embeddings are replaced with means
computed on a disjoint calibration set, which propagates corruption through the
whole forward pass, and then the clean activation at one (layer, position) is
written back. A position whose restoration recovers the original behaviour is
causally sufficient for it.

**Noising**, or mean ablation, replaces a position's activation with the mean
over a balanced calibration set, testing necessity rather than sufficiency
(Wang et al., 2023). Mean ablation does not move the model to a semantically
neutral state; averaging high- and low-confidence activations does not yield an
encoding of medium confidence, any more than averaging the embeddings of
"brilliant" and "terrible" yields "mediocre". It removes trial-specific
information.

**Representation swap** transplants a donor trial's activation at one position
into a recipient trial, in a 2×2 design crossing recipient class band with donor
class band. The same-band conditions (High→High, Low→Low) control for the
generic disruption any foreign activation causes; the cross-band conditions
(High→Low, Low→High) isolate transfer that depends on the donor's own reported
level. This is the interchange-intervention logic of Geiger et al. (2021).

**Attention knockout** sets the attention weight from a target position to a
source position to zero across all heads in a layer window, following Geva et
al. (2023). It maps information flow rather than representation content.
Blocking requires an eager attention implementation, since fused kernels can
silently ignore a custom mask.

## 2.5 Metrics

Four metrics recur. The **logit difference** is the logit of a target class
minus the mean logit of the alternatives,

$$
\Delta_{\mathrm{logit}}\bigl(z^{\omega}, y\bigr) \;=\; z^{\omega}_{y} \;-\; \frac{1}{K-1}\sum_{k \neq y} z^{\omega}_{k},
\tag{72}
$$

with the target $y$ always fixed at the clean prediction so that intervened and
clean runs are compared on the same quantity. Logit space is used rather than
probability space because the model's computation is linear in logits until the
final softmax (Wang et al., 2023; Heimersheim & Nanda, 2024). The **first-token
change rate** is the fraction of trials whose argmax class flips under
intervention. **Recovery** rescales a patched metric between the corrupt and
clean baselines, so that 100% is full restoration and 0% is no improvement over
corruption. **Spearman's rank correlation** $\rho$ measures agreement between a
self-report and a computed quantity; it is rank-based because the self-report is
ordinal and the computed quantities live on incomparable scales, ranging from a
bounded sequence probability to unbounded summed nats. Calibration is summarized
by **expected calibration error** (ECE) over ten bins with no temperature
scaling, and by the **area under the receiver operating characteristic curve**
(AUROC) for discriminating correct from incorrect answers.

Error bars throughout are the standard error of the mean (SEM) across trials.
An effect is read as present only when its error bar clearly separates from the
control position's.

## 2.6 Two levels of question

The extension in Chapter 6 rests on a distinction worth stating here. A
self-report can be interrogated at two independent levels.

The **mechanistic** level asks whether there is a causally manipulable internal
representation of the class the model is about to verbalize, and where in the
network it lives. Every intervention in §2.4 operates at this level. None of
them requires knowing whether the report is *true*. Steering PANL and watching
the reported class move is informative regardless of whether the class was
accurate.

The **validity** level asks whether the report tracks anything real. This is
where a ground truth is load-bearing, and it is the level at which confidence
enjoys an accident of convenience: trivia questions ship with gold answers, so
correctness is available at no cost. No comparable signal comes free for
"nuance" or "commitment". That is a fact about datasets, not about the
constructs.

## 2.7 Ontological vocabulary

Chapter 8 reads the results through William Benzon's account of ontological
structure in knowledge representation. Two of his terms are used, and both are
defined here on first use.

An **inheritance tree** in Benzon's sense organizes entities by the kind of
thing they are, in a hierarchy that he argues is orthogonal to the conventional
`isa` hierarchy of knowledge representation (Benzon, 1987). A **paradigmatic
transition** is a change within a category, his example being caterpillar to
butterfly: the thing stays the same kind of thing. An **ontological transition**
is a change of category, his example being living to dead. Benzon later applies
the same apparatus to LLMs, reporting that ChatGPT handles abstract targets
better than concrete ones in games of twenty questions (Benzon, 2023).

The evidentiary status of these two anchors is not the same, and this thesis
does not treat them as if it were. Kumaran et al. (2026) is a peer-reviewed
empirical paper at ICML with a full intervention battery behind each claim.
Benzon's work is descriptive and interpretive essay writing, distributed as
working papers, and is not itself empirically validated. It is used here as a
conceptual lens for interpreting mechanistic findings, and no claim in this
thesis rests on it as evidence.
