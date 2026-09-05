
## Discussion notes (2026-08-27)

Q&A against this codebase and `docs/manual/summary.md`, not new work — recorded here
because it clarifies read points worth not re-deriving later.

1. **Which experiment localizes the confidence encoding?** Experiment 6 (linear probing &
   variance partitioning, `vconf/exp6_probing.py`) is the *correlational* answer: PANL
   decodability rises with depth (correctness AUROC ~0.80 by L15–20; confidence-magnitude R²
   peaks around **L40**, adding 0.380 unique R² beyond all six log-prob baselines combined).
   But decodability isn't causal use — Exp 6 itself shows PANL+1 is equally decodable despite
   being causally inert everywhere else. The causal localization is only established jointly
   with Exp 1 (steering, peak L21–25 / L30–35), Exp 2 (patching, PANL peak L25 / CC from L30),
   Exp 3 (noising), Exp 4 (swap), Exp 7 (AC null), and Exp 8 (attention blocking: answer
   tokens → PANL L22–28 → CC L30–36 → unembedding).
2. **PANL+1, precisely** — confirmed against `vconf/prompts.py:201-245`: PANL is the `\n`
   immediately after `**Answer**: {answer}`; PANL+1 is the very next token, which for the
   `categorical`/`numeric` prompts is the first token of the confidence-instruction block
   (`CATEGORICAL_INSTRUCTIONS`/`NUMERIC_INSTRUCTIONS`), and for `minimal_numeric` (no
   instruction block) is the start of `MINIMAL_CUE` instead. Its only role across every
   intervention experiment is as the negative control.
3. **Smallest information set to determine the numeric confidence** — per
   `exp6_probing.py:26-46`'s headline numbers: six log-prob summaries alone → R²=0.100; PANL
   vector alone (~L40) → R²≈0.45; PANL + log-probs → ~0.48; CC vector alone (~L30–36, the
   last prompt token) → R²≈0.80, the best single predictor but trivially close to the output
   since it sits immediately before the sampled confidence token. None reach 1.0 — no set of
   activations is a fully deterministic function, only a strong statistical/causal one.
