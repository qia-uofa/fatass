# Build log

Work log for the reproduction code base in this directory (`thesis.experiment.code`),
built from `docs/manual/reproduction-guidebook.md` (§ references below are to that
document) on the machine `scripts/setup/_.sh` provisions.

## 1. Inputs read

* `docs/manual/reproduction-guidebook.md` — the full protocol (1,970 lines): research
  questions, prompts verbatim, positions, metrics, ten experiments, the §13 table of
  underdetermined details, the §14 validation table.
* `docs/manual/spec.md` — the condensed requirements spec; cross-checked against the
  guidebook, no contradictions found.
* `scripts/setup/_.sh` — the environment it leaves behind: conda prefix `/scratch/qi/env`,
  `$PROJECT_ROOT=/scratch/qi/project` with `data/raw/triviaqa`, `activations/`,
  `checkpoints/.hf_cache`, `results/{grades,logs,figures}`, and `~/.thesis-experiment.env`.

## 2. Environment findings (before writing any code)

| Finding | Consequence |
|---|---|
| `setup/_.sh`'s `torch>=2.3` resolved to **torch 2.13.0+cu130**; the driver is 12.6, so `torch.cuda.is_available()` was **False** | Installed `torch==2.10.0+cu126` (cp314 wheel) into the same conda prefix — the experiments require GPU execution (§2.1). 8× RTX A6000 48 GB then visible, bf16 supported |
| `pytest`, `jupyter`, `nbconvert`, `ipykernel` not installed by the setup script | Installed into the same prefix |
| `HF_TOKEN` empty and `google/gemma-3-27b-it` is a **gated** repo | The primary model of every main-text experiment cannot be downloaded here |
| `Qwen/Qwen2.5-7B-Instruct` ungated | Downloaded (15 GB) — it is the manual's own Axis-2 model (§12.2), so the default run is a real part of the study rather than a stand-in |
| `OPENAI_API_KEY` empty | GPT-4o-mini grading (§2.3.1) and the hedging check (§3.2) fall back to documented alternatives |
| TriviaQA present: 9,961 unique questions after dedup (manual expects ~11k) | Enough for every disjoint subset of §2.3.4 at the reduced scale |
| Big-Math / MMLU directories empty; the manual names no HF repo id for either | Loaders read the local directory and raise `DatasetNotProvisioned` naming that reason instead of guessing a source |
| `mistralai/Magistral-Small-2506` ungated but not cached (48 GB) | Axis 4's code path implemented; the notebook reports the checkpoint is absent and prints the expected results |

## 3. What was built

```
vconf/       20 modules, ~5,200 lines — the reusable package
notebooks/   10 notebooks, one per experiment section (§3–§12)
tests/       17 test modules, 244 tests, no model or dataset needed
README.md    layout, run profiles, choices, limitations
pytest.ini
```

Shared setup (§2) lives in `config/prompts/data/models/positions/pipeline/grading/hooks/
attention/activations/interventions/metrics/results/plotting`; each experiment gets its own
module `exp0_behavioral` … `exp9_generalization`, carrying the manual's expected values as
`PAPER_TARGETS` (and `PEAK_LAYERS`) so every notebook prints its result beside the paper's.

Design points worth recording:

* Prompts are reproduced character-for-character, including the en-dashes in the class
  ranges and the trailing apostrophe of the minimal numeric prompt (§2.5).
* Positions are located **per trial** from tokenizer offset mappings, never hard-coded
  (§2.6); the pure mapping functions are unit-tested on synthetic offsets.
* One hook utility serves steer / patch / noise / swap, applied at the decoder-layer output
  (§2.10, §13 #4); corruption for patching happens at the input-embedding level (§5.2).
* Attention knockout adds `−inf` at the `(t, s)` entries of the additive mask for the layers
  in a 12-layer window (§11.1–11.2), verified by asserting post-softmax attention is 0.
* All model/tensor computation runs on CUDA; `load_model` raises if CUDA is unavailable.

## 4. Decisions where the manual underdetermines

§13's fifteen items are implemented at the manual's recommended defaults. Four further
decisions were needed and are marked in the source and the README:

1. **Chat template with an assistant prefill** (§13 #2, which leaves the choice open but
   demands consistency): the prompt body is one user turn and the trailing cue
   (`**Confidence**:` / `**Answer**:`) is prefilled as the start of the assistant turn, so CC
   (respectively AC) really is the last token of the prompt as §2.6 requires. Exception: the
   minimal numeric prompt is fed raw, because that prompt exists to minimise the template
   tokens between PANL and CC and a chat template would reinsert turn markers there.
2. **Phase 0 for the minimal numeric prompt** uses the canonical §13 #12 categorical
   Phase-0 prompt — the minimal prompt has no instruction block to move to the front, only a
   cue, and using the cue produced digits as "answers".
3. **Trials whose PANL is not isolable are dropped** (§2.6, §14.3): accepted when the token
   starts exactly at the post-answer newline and is whitespace-only, so a merged `"\n\n"`
   blank line (numeric prompt) is fine but an answer ending in punctuation merging into
   `".\n"` is not. This costs ~78 % of Phase-0 generations on Qwen, which is why the
   behavioural pass draws six questions per usable trial.
4. **Clean baselines are recomputed with the intervention runs' own batching**
   (`interventions.compute_clean_logits`), because bf16 attention is not bit-exact across
   batch compositions and §2.8's metrics compare token-by-token against the clean run.

## 5. Bugs found and fixed while testing

| # | Bug | Fix |
|---|---|---|
| 1 | `CC->NL+1` split on `+` into "NL" and "1", blocking two edges instead of the PANL+1 control | `attention._source_positions` treats `NL+1`/`PANL+1` as one atom; regression test added |
| 2 | Qwen's `generation_config` sets `repetition_penalty=1.05`, so greedy `generate()` disagreed with the forward-pass argmax on numeric prompts (the digits appear in the prompt) | `repetition_penalty=1.0` passed explicitly on every generate path; §2.2 sanity check now matches |
| 3 | The §2.2 sanity check compared a re-encoded decoded string instead of token ids, and used padded batches | Rewritten to generate one prompt at a time and compare ids |
| 4 | Clean/intervened logits came from different batch layouts (see decision 4 above) | `compute_clean_logits`, wired into experiments 1–4, 7, 8 |
| 5 | PANL rejected whenever the tokenizer merged the numeric prompt's blank line → 0 usable numeric trials | Whitespace-only + starts-at-the-newline acceptance rule |
| 6 | Activation-store cache keyed by trial *count*, so a different 300 trials silently reused a stale `.npz` | Key includes a SHA-1 of the trial ids |
| 7 | Grade cache and activation store written non-atomically (notebooks run in parallel) | Temp file + `os.replace` in both |
| 8 | Donor matching preferred the same *question* bin over the same cell, inflating answer-length mismatch | Falls back to minimum total bin distance |
| 9 | **§2.3.4 violation**: steering vectors were extracted, and probes fitted, on the same trials they were tested on | `nb.split_activation_holdout`; all affected notebooks rewritten to take the activation set off the front and draw the calibration set and test trials from the holdout. Behavioural run raised 300 → 1,000 trials so the three sets can be disjoint |

## 6. Verification

* `pytest`: **244 tests, all passing** (`/scratch/qi/env/bin/python -m pytest`). Coverage
  spans prompt fidelity, position mapping, every metric, dataset dedup/partition, grading and
  its cache, hooks and embedding corruption, attention windows/pathways/masks, the
  intervention runner and activation store (against a tiny synthetic torch model), the tidy
  results layer, plotting, run profiles, and each experiment module's selection/vector/
  matching/partitioning functions.
* All ten notebooks were executed end-to-end with `jupyter nbconvert --execute` and verified
  cell-by-cell (no `error` outputs, every code cell executed). Two rounds:
  * **Round 1** (300-trial run, pre-fix-9): all ten clean.
  * **Round 2** (1,000-trial run, disjoint sets): **in progress** — notebook 0 done and
    verified; 1–3 running on GPU 0, 4–6 on GPU 1, 7–9 on GPU 2.

### Round-1 results (Qwen 2.5 7B, reduced scale) against the paper

| Quantity | Reproduction | Paper |
|---|---|---|
| Steering peak layers PANL / CC | L16 / L22 | Qwen L15 / L22 |
| Patching confidence recovery PANL / PANL+1 | 35.5 % / 9.2 % | 24.3 % / −1.4 % (Gemma) |
| Patching peak layers PANL / CC | L16 / L27 | Qwen L15 / L27 |
| Noising peak layers PANL / PANL+1 / CC | L16 / L5 / L22 | Qwen L11 / L6 / L21 |
| Swap at PANL, L→H / H→L Δconfidence | +0.16 / −0.05 | +0.21 / −0.09 |
| PANL R²_unique beyond all six log-prob baselines | 0.346 | 0.380 |
| log-prob → verbal confidence, cross-run / within-run r | 0.288 / 0.245 | 0.29 / 0.23 |
| AC vs PANL decoding R² | 0.14 vs 0.62 | 0.2 vs 0.75 |
| Attention blocking `ALL→A` → `_keepNL` | 0.42 → 0.38 (categorical) | 0.685 → 0.455 |
| Mean-log-prob correctness AUROC | 0.751 | 0.75 |

Two checks failed honestly rather than being tuned away, and both are explained in the
notebooks: the §8 patching drift is larger than the paper's because Gemma's residual streams
are far more concentrated than Qwen's (natural pairwise cosine p5 0.997 vs 0.67), and the six
log-prob baselines combined beat the best single one by more than the paper reports at this
sample size.

## 7. Known limitations of the committed run

* Runs under the **reduced** profile (`VCONF_PROFILE=reduced`, the default): Qwen 2.5 7B, a
  6-layer subset of its sweep, 1,000 behavioural trials, 24–32-trial test sets. Procedures,
  prompts, positions and metrics are the manual's; the scale is not. `VCONF_PROFILE=paper`
  selects Gemma 3 27B and the manual's own sizes and needs an `HF_TOKEN` with the licence
  accepted.
* Correctness labels come from normalised alias matching, not GPT-4o-mini, so accuracy and
  ECE are approximate; the manual's grader is implemented and used automatically once a key
  is present.
* Experiment 9 axes 3 (Big-Math, MMLU) and 4 (Magistral) report why they cannot run here and
  print the values to match, rather than being silently skipped.

## 8. Open issues

Ordered by what they block. Nothing here is a silent failure — each is visible in the
notebooks, the README, or a raised exception.

### Blocking completion of this task

| # | Issue | Detail |
|---|---|---|
| O1 | **Round-2 notebook execution unfinished** | Notebooks 0–2 re-executed and verified against the 1,000-trial disjoint split; 3–9 still running (GPU 0: 3; GPU 1: 4–6; GPU 2: 7–9). Until they finish, the committed outputs for 3–9 are from round 1 (pre-§2.3.4-fix) and must not be read as final. |
| O2 | **§6 of this log is stale** | Its results table holds round-1 numbers. Replace with round-2 numbers once O1 completes. |

### Cannot be resolved on this machine

| # | Issue | Detail |
|---|---|---|
| O3 | **Gemma 3 27B never run** | Gated repo, `HF_TOKEN` empty. Every main-text number in the manual (§3–§11) is Gemma's; the `paper` profile targets it but has never been executed, so that code path is untested at 62 layers and 27 B parameters — including the `device_map="auto"` sharding branch of `load_model`. |
| O4 | **Correctness labels are not the paper's** | No `OPENAI_API_KEY`, so grading falls back to normalised alias matching. That is stricter than an LLM grader on TriviaQA, so accuracy is pessimistic (67.2 % here) and ECE inherits the bias. `grading.gpt4o_mini_grader` is implemented and takes over automatically when a key exists, but has never made a real API call. |
| O5 | **Experiment 9 Axis 3 unrun** | The manual gives no Hugging Face repo id or configuration for Big-Math or MMLU, so nothing is downloaded; the loaders raise `DatasetNotProvisioned` naming exactly that. The accuracy anchors to match (40.2 % / 76.8 %) are printed instead. |
| O6 | **Experiment 9 Axis 4 unrun** | `mistralai/Magistral-Small-2506` (48 GB) is not in the local cache. The whole CoT path is implemented — `run_magistral_phase0`, the trace-carrying Phase-2 prompt, `stratified_activation_set`, `magistral_corruption_spans`, trace-length donor matching, the ten `Trace k%` probe positions — and is covered by unit tests on synthetic prompts, but has never touched the real checkpoint. |

### Known deviations that survive into the results

| # | Issue | Detail |
|---|---|---|
| O7 | **§8 OOD control does not replicate the paper's equal-drift finding** | At the peak layer, patching's pre-patch cosine similarity differs markedly between PANL and PANL+1 on Qwen, where the paper reports 0.999 at both on Gemma. The cause is visible in the same notebook: Qwen's *natural* pairwise cosine p5 is ≈0.67 versus Gemma's 0.997, so its residual streams are far less concentrated and every drift measure sits lower. The steering control — the one Experiment 1's claim rests on — does stay inside the natural distribution. |
| O8 | **The six log-prob baselines beat the best single one by more than the paper reports** | Combined R²_CV ≈ 0.22 versus best single ≈ 0.16 (paper: 0.100 vs 0.101). With 300 activation trials the combined regression has more freedom than at n = 3,000. The headline §9 result is unaffected — PANL still explains large unique variance beyond all six. |
| O9 | **Donor–recipient length matching falls short of §7.3's targets** | The paper matches question-length bins 100 % and answer-length bins 94–100 % out of hundreds of donors per band; the reduced low-confidence pool gives ~0.46 / ~0.83 on the cross-confidence cells with mean \|ΔL_A\| of several tokens. Reported in the notebook's matching-quality table beside the paper's targets, because a residual length mismatch is the one artifact that could masquerade as confidence transfer. |
| O10 | **~78 % of Phase-0 generations are discarded** | A trial is dropped when the tokenizer merges the post-answer newline into the answer's last token (§2.6, §14.3). Qwen's answers are often long sentences ending in punctuation, so the yield is ~22 % on the categorical prompt and ~10 % on the numeric one. This costs generation time and biases the retained set toward short answers — which is the regime the paper's TriviaQA answers are in, but it is a selection effect worth stating. |
| O11 | **Numeric-prompt interventions measured on the first digit only** | §12.1's own caveat: confidence is multi-token ("95"), all interventions happen during prefill, and later digits reflect both the intervention and propagation through earlier generated tokens. The module records the full generated integer for calibration but the intervention metrics use the first digit, as the manual recommends. |

### Fragilities to watch

| # | Issue | Detail |
|---|---|---|
| O12 | **The torch repair is undone by re-running `setup/_.sh`** | The setup script installs `torch>=2.3`, which resolves to a CUDA 13 build this driver cannot use. Re-running it will regress CUDA availability; reinstall `torch==2.10.0+cu126` afterwards. The same applies to `pytest`/`jupyter`, which the setup script does not install. |
| O13 | **Attention-mask shape assumptions** | `attention_knockout` handles a 4-D float mask, a dict of masks, and a missing mask (building a causal one). Only the 4-D tensor path is exercised by Qwen with `attn_implementation="eager"`; the other two branches are defensive and covered only by unit tests against a stub layer. |
| O14 | **Batched bf16 attention is not bit-exact** | Logits for the same prompt differ by up to ~0.6 between batch layouts, which can flip an argmax when the top two class tokens are close. Handled by computing every clean baseline with the intervention runs' own batching, but it means absolute first-token change rates carry a small floor of numerical noise. |
| O15 | **Grade cache is keyed by (question, answer, aliases)** | Changing the Phase-0 prompt or generation settings produces new answers and therefore new cache entries rather than stale hits — correct, but the file grows monotonically and is never pruned. |
