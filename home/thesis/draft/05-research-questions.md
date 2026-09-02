# 4. Research Questions and Conceptual Framework

## 4.1 The four questions

**RQ1 (ontological).** What kind of entity is an LLM "belief", and what would
count as evidence for each candidate answer?

Three candidates were named in §1.2. A belief could be a *representational
state* the model has, with the verbal report reading it out. It could be a
*linguistic performance* the model executes, with the report being the kind of
text this prompt calls for and no belief standing behind it. It could be an
*observer-relative artifact*, constituted by the extraction procedure rather
than found by it. Evidence for the first would be a dedicated internal state,
specific to the reported construct, that is causally engaged when the model
verbalizes. Evidence for the second would be a mechanism that produces the
report without any construct-specific internal state being involved. Evidence
for the third would be that varying the extraction procedure, while holding
model and question fixed, varies what gets measured.

**RQ2 (reproduction).** Does the internal/verbal dissociation reported by
Kumaran et al. (2026) replicate at reduced scale, on a different model from
their primary one?

This is the prerequisite. If the anchor result does not survive independent
re-implementation, nothing built on top of it is worth interpreting.

**RQ3 (generalization).** Does the same dissociation hold for other
self-reportable epistemic constructs, or is confidence special?

**RQ4 (synthesis).** What does the combined RQ2 and RQ3 pattern license, and
what does it not?

## 4.2 The discriminating logic, stated in advance

RQ3 is designed so that either outcome is a result, and it is worth stating
which outcome points where before any data is presented, so that the results
chapters can be read against a fixed standard rather than toward a preferred
conclusion.

If the cache-then-verbalize architecture **generalizes** across constructs,
that is evidence for a general computational strategy: the model routes
information about whatever property the prompt names to the forced completion
cue, and does so at the post-answer position regardless of what the property
is. That pushes away from the reading on which confidence is a special
introspective state, because a state that shows up identically for
"commitment", "nuance", "variety" and "impurity" is not plausibly a dedicated
confidence representation. It is compatible with both the linguistic-performance
reading and the observer-relative reading.

If the architecture **fails to generalize**, that is evidence in the other
direction. A mechanism that operates for confidence and not for structurally
analogous constructs is doing something distinctive, which is what a dedicated
representational state would look like.

There is a third possible outcome, and Chapter 7 reports that this is the one
that occurred: the experiments may fail to establish the mechanism for *any*
construct at the available scale, including for confidence at the position
where the anchor paper finds it. That is neither of the two answers above. It
is a statement about the sensitivity of the reduced-scale replication, and §7.4
treats it as such rather than reading it as evidence against the mechanism.

## 4.3 The two levels, and why the split matters here

§2.6 distinguished the mechanistic level from the validity level. The
distinction does real work for RQ3, because the two levels answer differently
to the objection that only confidence has a ground truth.

At the mechanistic level, a ground truth plays no role. Steering PANL for the
"nuance" construct and observing whether the reported nuance class moves is a
well-posed experiment whether or not "nuance" has an objective referent. The
paper's own steering experiment ranks its extraction pool by the model's *own*
reported confidence, not by correctness; correctness enters only as an optional
restriction on which trials are eligible. The mechanism question transfers to
any Likert-scaled self-report at no conceptual cost.

At the validity level, a ground truth is exactly what is at stake, and here
confidence's advantage is real but narrower than it looks. Confidence has
correctness available because TriviaQA ships gold answers. That is a property of
the dataset. Chapter 6 shows that computable counterparts exist for the other
constructs too: sequence probability for commitment, answer entropy for nuance,
embedding spread for variety, Gini impurity of an induced partition for
impurity. None of these is handed over for free the way correctness is, and
each involves a design choice about what the self-report is a report *about*.
That choice is itself an ontological commitment, and §8.5 returns to it.

## 4.4 The bounded claim

The strongest conclusion this thesis is prepared to defend, stated here so that
Chapters 8 and 10 can be checked against it, is:

> The pattern of results is more consistent with an information-caching and
> retrieval architecture than with a naive introspective self-report framing.

Three things this deliberately does not say. It does not say the model has no
introspective access, only that the evidence does not require positing it. It
does not say the cached state *is* a belief, or that it is not. It does not say
which of the three readings in §4.1 is correct; the results pressure one of
them and leave the other two open, which §8.4 spells out.

The reason for stating the claim this narrowly is not modesty. It is that the
extension is correlational at the validity level and, at the scale actually
run, largely null at the mechanistic level, and a stronger claim would be one
notch beyond what was shown.

## 4.5 Which chapter answers which question

RQ2 is answered in Chapter 5, with the reproduction's own failures reported in
§5.6 and §5.7 rather than folded into the positive result. RQ3 is answered
across Chapters 6 and 7: the method that makes the question askable in Chapter
6, the calibration and steering results in Chapter 7. RQ1 and RQ4 are answered
in Chapter 8, as far as the evidence permits, with Chapter 9 stating the limits
explicitly.
