# Coverage Check — Brainstorm Dialogues vs. `_.md` Outline

**Verdict: gaps found.** The outline covers the experimental spine, the ontological argument, and the regulatory front matter well; ~8 items raised across the dialogues are unaddressed, one of them substantive (the construct inventory no longer matches the epistemic-emotion rationale the dialogues settled on).

---

## Gaps — raised in brainstorm, not clearly addressed

- **Epistemic-emotion constructs never appear (`20260827-083843`, `20260827-043417`)** — the sessions converged on *surprise* (+ *confusion* or *doubt*) as the extension states, with predictive perplexity / expectation-mismatch as surprise's independent ground truth, explicitly justified by Benzon's ontological-transition framing. The outline's Ch. 6.3 inventory is confidence / commitment / nuance / challenge / variety / impurity — none of them an epistemic emotion. Ch. 3 still cites the epistemic-emotions literature as "justification for choosing knowledge-appraisal constructs", so the stated rationale and the actual constructs no longer match. Either drop that Related Work justification or explain the pivot.
- **Second epistemic state pick (confusion vs. doubt) (`20260827-083843`)** — logged as an unresolved open item; the outline neither resolves nor records it.
- **Thesis length / page budget (`20260831-073832`)** — "is there a length requirement" was asked and never answered (search cut off by the Themenausgabe email). No page budget anywhere in the outline, though Ch. 5-vs-6/7 chapter split and the "switch if Ch. 5 is short" note both depend on one. Also unresolved: the LMU-vs-Goethe page-rule mis-attribution flagged in `search-notes.md`.
- **The exemplar thesis found (`20260831-073832`)** — Groot 2024, *Confidence is Key: Uncertainty Estimation in LLMs and VLMs* (Groningen), downloaded to `thesis/examples/`. Not cited or positioned anywhere in Ch. 3.
- **Linguistic theories of the internal/verbal gap (`20260826-064558`)** — speech-act theory, assertion/sincerity conditions, Gricean pragmatics, epistemic modality/evidentiality/hedging were raised as the framing for what the gap *means*. Outline keeps only the mechanical `exp0` hedging check; Ch. 8's "linguistic performance" reading has no linguistics literature behind it. (Partly superseded when Benzon was made the anchor — but the "performance" reading is currently asserted without a source.)
- **Other ground-truth-bearing constructs (`20260827-111955`)** — Jigsaw toxicity, stance (SemEval), formality (GYAFC), IMDB, and *forecasting calibration against resolved outcomes* (flagged as "closest in spirit to the paper's framing") were all enumerated. Ch. 10 future work keeps only SST-2 / GoEmotions.
- **QA-framing limitation (`20260827-111955`)** — the point that the question→answer→rate-yourself structure itself doesn't generalize to non-confidence constructs is a named non-replaceable piece; Ch. 9 lists ground-truth-of-convenience limits but not this framing limit.
- **Oberseminar + second examiner (`20260826-064558`)** — concluding presentation within 4 weeks of submission, and the second-examiner proposal form due by the submission deadline. Not in the front-matter/regulatory section. (Deliverables around the thesis, not document sections — include only if that section is meant to be the full compliance checklist.)

*Not counted as gaps (administrative, no structural implication):* repeat-after-fail procedure and `soll` semantics (`20260826-083219`); extension/illness-certificate rules; 9-week timeline and `timeline.md`; submission logistics (3 bound copies, USB / Hessenbox, foyer mailbox); the `n_trials` runtime-scaling analysis (its conclusion *is* in Ch. 6.7).

---

## Outline content with thin brainstorm grounding

- **Ch. 6.3 construct inventory + Ch. 7.2–7.5 experiment grid** — commitment, nuance, challenge, variety, impurity and the `TemperatureGT` control were never discussed in any dialogue; they enter only as a one-line codebase-survey summary in `20260831-073832`. Grounded in the code, not in any recorded decision.
- **Ch. 5.7 self-audit of the reproduction** — sourced from `diagnoses.md`; no dialogue raises the reproduction's own incompleteness as a reportable result.
- **Ch. 5.8 non-obvious implementation decisions** — same: codebase-derived, not brainstormed.
- **Appendices A–F** — conventional, but no dialogue discusses them.
