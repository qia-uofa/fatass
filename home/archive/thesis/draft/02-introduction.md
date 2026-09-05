# 1. Introduction

## 1.1 Two signals from one model

Ask a large language model (LLM) a factual question and it produces an answer.
Ask it, in a second step, how likely that answer is to be correct, and it
produces a second thing: a verbal report about the first. The two are separate
outputs of the same network, and they are computed at different token positions
and, as it turns out, at different depths.

That separation is easy to overlook because both come back as text in the same
conversation. It matters because the second output invites a reading that the
first does not. When a model says "Highly likely", the natural interpretation is
that it has consulted some internal state and described it. That interpretation
attributes to the model something belief-like: a state it has, which the report
is about. Whether anything of the sort is there is an empirical question about
where in the network the report's content comes from, and it is exactly the
question Kumaran et al. (2026) put to Gemma 3 27B, Qwen 2.5 7B and Magistral
Small 24B. Their answer is that confidence-relevant information is assembled
during answer generation, cached at the newline immediately after the answer,
and retrieved later when the verbalization is demanded. The model does not
compute its confidence when asked. It has already computed it.

## 1.2 The ontological question

Suppose that result holds. What does it license us to say about the model?

At least three readings survive it. On the first, the cached state is a
**representational state** the model has: an internal variable carrying
information about answer quality, which the verbal report reads out. On the
second, the report is a **linguistic performance**: the model produces the kind
of hedge that a text like this one calls for, and the cached state is part of
the machinery that produces well-formed text rather than a belief about
anything. On the third, the "belief" is an **observer-relative artifact**: what
gets measured is whatever the extraction procedure (a prompt, a forced cue, a
token position, an argmax over ten class names) constructs, and a different
procedure would have constructed something else.

Confidence alone cannot separate these. Every mechanistic fact established
about confidence is a fact about one construct, and all three readings can
accommodate one construct. What discriminates them is how the mechanism behaves
across a *family* of self-reports. If the caching architecture is specific to
confidence, that favours the first reading: confidence would be doing something
the others do not, which is what a dedicated internal state looks like. If the
same architecture appears for any self-report the prompt asks for, that pushes
toward the second and third: the mechanism would be a general property of how
the model routes information to a forced completion cue, and "confidence" would
be one label among many for the same machinery.

This is why the thesis is titled around beliefs rather than confidence. The
officially issued title is *An Ontological Perspective on LLM Beliefs*; the
working title during most of the project was "...LLM Confidence". The shift is
not cosmetic. Confidence is the one belief-like self-report that happens to have
an independent correctness signal handed to it for free, because trivia
questions come with gold answers. Treating it as the whole object of study
mistakes a convenience of the dataset for a property of the model. Throughout
this document, "belief" names the general object (a verbally reported epistemic
self-attribution), and "confidence" names one specific instance of it, measured
by one specific procedure.

## 1.3 Contributions

This thesis makes three contributions, in the order the chapters present them.

**An independent reproduction at reduced scale.** Chapter 5 reports a full
re-implementation of Kumaran et al.'s ten experiments as a Python package
(`vconf`) with one notebook per experiment and a unit test suite. The paper's
primary model, Gemma 3 27B, could not be executed on the available hardware for
a reason documented in §5.6; every result reported here is therefore from
Qwen2.5-7B-Instruct, which is the paper's own second architecture. The
reproduction confirms the central claim and fails to confirm two of the paper's
six intervention results at this scale. Both outcomes are reported, along with
a self-audit of the reproduction's own gaps (§5.7).

**A generalized observation-method × ground-truth framework.** Chapter 6
introduces `vonto`, a second package built alongside the first rather than by
renaming it, so the reproduction stays runnable. Its load-bearing idea is that a
self-report construct decomposes into two independent objects: an
**ObservationMethod**, which is what gets elicited, and a **GroundTruth**, which
is what the elicited value is checked against. The decomposition matters because
it separates two questions that the confidence literature runs together. Whether
there is a causally manipulable internal representation of the class the model
is about to verbalize requires no ground truth at all. Whether the report tracks
anything real does. Six observation methods, seven ground truths and four
datasets are implemented in this frame, one of the ground truths being a control
column the model never sees.

**A bounded ontological reading.** Chapter 8 puts the resulting pattern against
the three readings above, using William Benzon's vocabulary of inheritance trees
and ontological versus paradigmatic transitions (Benzon, 1987, 2023) as the
interpretive lens. The conclusion the evidence supports is narrow, and Chapter 4
states it in advance so that the results chapters can be read against it rather
than toward it: the pattern is more consistent with an information-caching and
retrieval architecture than with naive introspective self-report. It does not
resolve what kind of entity an LLM belief is. Benzon's framework is used here as
a conceptual lens, not as an independently validated empirical claim; the
asymmetry between it and the peer-reviewed anchor paper is discussed in §2.7.

## 1.4 Reading guide

Chapter 2 defines the protocol, the token positions, the intervention
primitives, the metrics and the ontological vocabulary that the rest of the
document uses. Chapter 3 places the work in its literature. Chapter 4 states
four research questions and the logic by which the evidence bears on them.
Chapter 5 answers RQ2 (does the dissociation replicate?). Chapters 6 and 7
answer RQ3 (does it generalize beyond confidence?), the first describing the
method and the second the results. Chapter 8 answers RQ1 and RQ4 as far as the
evidence allows. Chapter 9 states what the evidence does not allow, and
Chapter 10 closes.

A reader who wants only the empirical outcome can read §5.5, §5.6, §7.4 and
§7.5. A reader who wants only the argument can read Chapter 4 and Chapter 8.
