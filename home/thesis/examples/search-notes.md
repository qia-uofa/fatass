# Comparable-thesis search — notes (2026-08-31)

Searched for past bachelor's/master's theses matching this profile (Goethe
Uni Frankfurt CS, advised by Ramesh; replicating + extending Kumaran et al.
2026 on LLM verbal confidence; philosophical/ontological framing via
Benzon). Quality over quantity, per the intent of `search@thesis.examples`
(`fatass/topology/thesis/examples/search.py`) — this was done by hand
(direct WebSearch/WebFetch) rather than running that transform, since its
second step opens an interactive `claude` window (`silent=False`) that
would hang on this headless machine, and the student profile it would
extract was already on hand in `brainstorm/profile.md`.

## Found and saved

**`Groot_2024_ConfidenceIsKey_UncertaintyEstimation_LLM_VLM.pdf`**
Tobias Groot, *"Confidence is Key: Uncertainty Estimation in Large Language
Models and Vision Language Models"* — Bachelor's thesis, Artificial
Intelligence, University of Groningen, 2024 (supervisor M. Valdenegro
Toro). Closest real match found: same degree level, same core empirical
object (LLM confidence/calibration, multiple models tested, calibration
error as the headline metric). No philosophical/ontological framing and no
reproduction-of-a-specific-paper structure, so useful mainly for the
empirical confidence-calibration chapters, not for Ch. 6-8's argument.
Source: https://fse.studenttheses.ub.rug.nl/32044/

## Searched for but not found (downloadable, matching)

- A student thesis (not a published paper) combining mechanistic
  interpretability *and* philosophy-of-mind/ontology framing — this
  specific combination appears to be genuinely novel; search kept
  surfacing arXiv papers and journal articles, not theses, e.g. "Embodied
  Explainability and Ontological Obstacles" and "Speech Acts and Large
  Language Models" (philarchive.org) — neither a downloadable student
  thesis, both closer to Related Work citations than structural examples.
- Any Goethe Uni Frankfurt Informatik bachelor thesis on an LLM-adjacent
  topic, to use as a *local* structural/formatting exemplar. None turned
  up in open search; the department's own thesis archive isn't
  web-indexed as far as I could find.
- A "reproduce a specific ML paper + extend it" bachelor's thesis
  matching Ch. 4-7's two-part structure. Found only general
  meta-research on ML reproducibility (Penn State, ReproducedPapers.org),
  not a comparable single-paper reproduction thesis.
- Considered and rejected: Huaranga Junco's MSc thesis "Distilling
  ontologies from large language models" (UPM) — same word "ontology" but
  a different sense (formal domain-ontology extraction, not the
  ontological-status-of-confidence question this thesis asks). Skipped
  as a likely-misleading match.

## One correction worth recording

A search pass surfaced "Goethe Uni Informatik bachelor theses: max 30
pages, structured Einleitung/Theorie/Ergebnisse page budget, half-page
German+English Zusammenfassung, preferably LaTeX" — checked this directly
before trusting it, and it's **not Goethe's rule**. It's LMU Munich's CIS
department guideline (cis.lmu.de/bsc/bachelorarbeit/richtlinien), which
the search summary had mis-attributed. Goethe's actual §35 PO 2019 (see
`brainstorm/profile.md`'s Open Items) states no page limit and no
prescribed chapter structure — don't treat the LMU numbers as binding.
