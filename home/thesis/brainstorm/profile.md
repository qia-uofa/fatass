# Thesis Profile

## Title
Ontological Perspective on LLM Confidence

## Institution
Goethe University Frankfurt, CS Bachelor's Thesis — Advisor: Visvanathan Ramesh

## Motivation
Large language models produce two distinct signals about their own answers: an
internal, sub-symbolic representation (hidden-state / cached activation at the
answer-adjacent token) and a verbalized, symbolic self-report (a categorical
confidence statement in natural language). Kumaran et al. (2026, "How do LLMs
Compute Verbal Confidence?") show these are computed separately — confidence
is cached at answer time and retrieved later at verbalization — and that the
cached signal correlates with, but carries more information than, the
verbalized output or raw token log-probabilities. This thesis treats that gap
as more than an engineering curiosity: it raises the philosophical question of
what kind of thing "confidence" actually is in these systems. Is it a
representational state the model *has*, a linguistic act the model
*performs*, or an artifact that only exists relative to the observer's
extraction method? Different answers carry different implications for how
trustworthy, meaningful, or even coherent talk of "LLM confidence" is.

## Research Questions
1. **(Ontological)** What kind of entity is "LLM confidence" — an internal
   representational state, a linguistic performance, or something that only
   exists relative to a particular measurement/extraction procedure? What
   would count as evidence for each position?
2. **(Empirical replication)** Does the internal/verbal confidence dissociation
   reported by Kumaran et al. replicate under the same or comparable setup?
3. **(Empirical extension)** Does the same dissociation pattern hold for other
   affective/epistemic states beyond confidence (e.g. surprise, hedging/doubt,
   basic affect categories), or is confidence a special case?
4. **(Synthesis)** What does the empirical pattern (replicated + extended)
   imply for the ontological question in RQ1 — does it support treating
   confidence as a genuine internal state distinct from its verbal expression,
   or does it undercut that framing?

## Methodology
- **Replication**: reproduce Kumaran et al.'s core experiment — extract the
  cached confidence signal from the answer-adjacent token, compare against
  (a) the model's own verbalized categorical confidence and (b) raw
  log-probabilities, on the same/comparable models (e.g. Gemma 3, Qwen 2.5)
  and datasets (TriviaQA, MMLU, BigMath).
- **Extension**: apply the same extraction + verbal self-report design to a
  small set of additional epistemic/affective states (candidates: surprise,
  doubt/hedging, or Ekman basic affect categories, to be narrowed down).
  Framed as a consistency claim (does the internal signal correlate with the
  model's own later self-report?) rather than a claim about "true" internal
  emotion, to keep the empirical scope tractable for a bachelor's thesis.
- **Philosophical framing**: use the empirical replication + extension
  results as evidence in a discussion of the ontological status of these
  internal signals, anchored on William L. Benzon's ontology work — "Ontology
  in Knowledge Representation" (1985/87, inheritance trees, paradigmatic vs.
  ontological transitions) and "ChatGPT's Ontological Landscape" (2023) —
  which supply the ontological vocabulary and framework applied to the
  empirical confidence-encoding results. Benzon's story-generation papers
  ("ChatGPT tells stories..." 2023/2024) are a secondary, looser source on
  latent hierarchical structure shaping surface output, usable as supporting
  analogy if relevant.

## Contribution
- A replication of a recent (ICML 2026) result on LLM confidence
  representations, independently verifying its core claim.
- A novel extension testing whether the internal/verbal dissociation
  generalizes beyond confidence to other epistemic/affective states.
- A philosophical framing that uses the empirical results to argue for (or
  against) a specific ontological account of what "LLM confidence" is,
  connecting an empirical NLP/interpretability result to philosophy of
  mind/language literature.

## Structure
1. Introduction — motivate the ontological question via the empirical
   internal/verbal gap; state contributions.
2. Related Work — Kumaran et al. and calibration/uncertainty literature;
   Benzon's ontology-in-knowledge-representation framework as the
   philosophical anchor.
3. Background — token probabilities, hidden states/activations, what
   "confidence" means technically; the philosophical vocabulary needed
   (ontology, representation, speech acts).
4. Methodology — replication setup, then extension setup.
5. Results — replication results, then extension results.
6. Discussion — the ontological argument: what do the results imply about
   what LLM confidence *is*.
7. Limitations
8. Conclusion & Future Work

## Open Items
- Confirm the specific extra epistemic/affective states to test in the
  extension (RQ3).
- Verify Goethe CS-specific CP threshold and any department-specific
  deviations from the Bioinformatik-template Merkblatt already reviewed.
