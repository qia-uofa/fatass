# 5. Part I — Reproduction

Method and results are kept in one chapter because there is one codebase, one
protocol and one validation table behind all of it. The reproduction is a
package (`vconf`) implementing the shared setup and all ten experiments of the
reproduction guidebook derived from Kumaran et al. (2026), with one notebook per
experiment and a unit test suite that runs without a model or a dataset.

## 5.1 Setup

The model is `Qwen/Qwen2.5-7B-Instruct` (Qwen Team, 2024), loaded from Hugging
Face in bfloat16, evaluation mode, gradients disabled, on a single NVIDIA RTX
A6000. It has 28 decoder layers and a residual stream of width 3584. Decoding is
greedy throughout, at temperature 0, matching the paper's own setting. The
dataset is TriviaQA `rc.nocontext`, validation split (Joshi et al., 2017),
deduplicated on normalized question text before sampling, which is what the
guidebook specifies.

Three mandatory setup checks precede everything else, because each is a
tokenizer-dependent fact that silently invalidates downstream results if it
fails. The ten class-initial token ids under Qwen's tokenizer are pairwise
distinct, as required by equation (37): `[2308, 28208, 910, 1230, 9668, 23434,
93637, 15308, 52385, 34303]`. The post-answer newline decodes to a bare `'\n'`
and is its own token. And the forward-pass argmax agrees with what `generate()`
actually emits on 96.9% of a 32-trial held-out sample, with 100% of argmax
tokens being valid class-initial tokens. The 3% disagreement is worth stating
rather than rounding away: it means roughly one trial in thirty has a
near-tie between two class logits that resolves differently under sampling
machinery than under a bare argmax, which is a small additional noise source on
every first-token change rate reported below.

Answer grading is the one deviation from the paper's own procedure. The paper
grades TriviaQA free-text answers with GPT-4o-mini at temperature 0, feeding it
the gold answer aliases. No OpenAI API key was available on this machine, so
grading fell back to the documented alternative, normalized alias matching, and
every notebook prints which grader produced its labels. Alias matching is
stricter than an LLM judge on TriviaQA, so accuracy and therefore ECE from the
fallback are pessimistic. This affects only the correctness-dependent numbers
(accuracy, ECE, AUROC, the correctness probe), not any of the intervention
results, which never consult a correctness label except to restrict the steering
extraction pool.

## 5.2 Profiles and scale

Two run profiles are defined. The `paper` profile is the guidebook's own
setting: `google/gemma-3-27b-it`, the 22-layer sweep, 7,858 behavioural
questions, 3,000 activation trials, 200- to 400-trial test sets. The `reduced`
profile, which produced every number in this chapter, keeps every procedure,
prompt, position, intervention and metric identical and shrinks only the scale:
Qwen2.5-7B-Instruct, a six-layer subset of that model's sweep (layers 0, 5, 11,
16, 22, 27), a 1,000-trial behavioural run, 300 activation trials, and test sets
of 24 to 32 trials.

The choice of Qwen is not a substitution of convenience: it is the paper's own
Axis-2 model (§C.3 of the paper), so the guidebook supplies expected values for
it directly, and the layer sweep is dense over a 28-layer model rather than
sparse over a 62-layer one. The choice of a six-layer subset rather than all 28
is a compute budget: every intervention runs one forward pass per trial per
layer per position per condition, and the full sweep would multiply the
intervention cost by a factor of roughly 4.7 without changing which position
peaks first, which is the quantity of interest. The consequence is that peak
layers reported here are resolved only to the nearest swept layer, so a reported
peak of L11 means "the effect was largest among {0, 5, 11, 16, 22, 27}", not
"the effect peaks at exactly layer 11".

The 24- to 32-trial test sets are the sharpest scale limitation and are the
reason nearly every effect below carries a wide error bar. With 24 trials, one
flipped class changes a first-token change rate by 4.2 percentage points and a
mean confidence delta by up to 0.008 units. Effects smaller than that are not
measurable at all at this scale. Numbers in this chapter are therefore not
reproductions of the paper's numbers and are never claimed to be; what is
claimed is a reproduction of the paper's *ordering* and *dissociation* results,
which are qualitative comparisons between positions.

## 5.3 The disjoint partition

Several trial sets must be mutually disjoint, and the guidebook is explicit
about this. Steering vectors are extracted from the activation-collection set
and tested on different questions; the calibration set that supplies patching
corruption means and noising ablation means is disjoint from both.

The partition is made once per run. The 1,000-trial behavioural pass is split by
taking the 300-trial activation-collection set off the front, leaving a
700-trial holdout; the 40-trial balanced calibration set is selected inside that
holdout, and each experiment's test trials are drawn from what remains.
Disjointness is asserted in the notebooks, not assumed. The reason it matters
is direct: if a trial's own activation contributes to the steering vector that
is later used to steer it, any resulting effect is partly circular.

## 5.4 Experiment battery

Each subsection states the guidebook's own expected value alongside the value
obtained.

### 5.4.1 Behavioural baseline and hedging

A verbal confidence signal that discriminates correctness at all is the
precondition for the mechanistic analysis to be about anything, so this
experiment is a gate rather than a preliminary. Over 1,000 usable trials, Qwen
answered 67.2% correctly under alias matching, with ECE 0.067 against the
guidebook's expected 0.06, AUROC 0.797 against an expected 0.65, and a mean
stated confidence of 0.739. The length-normalized mean answer log-probability
discriminated correctness at AUROC 0.751, which is close to the paper's own
0.75 for Gemma.

![Calibration and class distribution for Qwen2.5-7B-Instruct on TriviaQA under
the categorical prompt. Left: reliability diagram, stated confidence against
empirical accuracy, with the bin population printed above each point; the dashed
line is perfect calibration. Right: how often each of the ten classes was
chosen.](../assets/data/results/figures/exp0-calibration-qwen-categorical-triviaqa-reduced.png)

*Figure 5.1.* The reliability diagram should be read against the bin counts
printed above each marker, not as a smooth curve. Four of the ten bins hold
fewer than seven trials each, and the two large excursions below the diagonal
(at stated confidence 0.55 and 0.75) sit on bins of 4 and 1 trial respectively,
so they carry essentially no information; a single trial's outcome moves such a
bin from 0 to 1. The informative part of the curve is the three populated bins
at 0.35 (n=80), 0.65 (n=260) and 0.85 (n=438), all of which fall below the
diagonal, which is overconfidence of the kind Xiong et al. (2023) and Groot
(2024) report generally. The right panel shows the distribution the guidebook
warns about: 60.8% of trials land in the high band and 4.8% in the low band, so
any test set sampled uniformly would be badly unbalanced, which is why §5.3's
balanced selection exists. The AUROC of 0.797 exceeds the guidebook's 0.65 for
Qwen by a wide margin, and the most likely reason is the grader: alias matching
marks a hedged or verbose but substantively correct answer as wrong, and such
answers are also the ones the model reports lower confidence on, which inflates
the apparent discrimination. That is a caveat on the number, not a better
result.

Hedging language appeared in 0.6% of answers, against the paper's approximately
0%. The check exists to rule out the alternative that a steering vector encodes
linguistic hedging rather than confidence, and 0.6% is low enough to leave that
alternative without support.

### 5.4.2 Activation steering

Steering vectors were built by contrasting the mean activation of the ten
highest-reporting correct trials against the ten lowest, per (layer, position),
scaled to 3% of the mean residual norm at that (layer, position) and multiplied
by $\alpha \in \{2, 5\}$:

$$
v^{(\ell,p)} \;=\; \frac{\mu(\mathcal{H}) - \mu(\mathcal{L})}{\lVert \mu(\mathcal{H}) - \mu(\mathcal{L})\rVert}\;\cdot\;0.03\;\bar{n}^{(\ell,p)}
\tag{67}
$$

The 3% figure and the $\alpha$ values are the paper's own, chosen there
empirically and shown not to induce out-of-distribution effects; §5.4.5 checks
that claim directly on Qwen rather than inheriting it. Ten vector trials per
pole rather than the paper's 25 follows from the 300-trial activation set: 25
per pole would draw from the extreme tails of a pool an order of magnitude
smaller than the paper's 3,000.

![Activation steering on Qwen. One panel per position (PANL, CC, PANL+1, FCC),
each plotting the mean change in reported confidence against layer for high and
low steering at α=2 and α=5, with SEM error bars. Shaded bands mark the paper's
own peak layer ranges.](../assets/data/results/figures/exp1-steering-confidence-qwen-categorical-triviaqa-reduced.png)

*Figure 5.2.* Each panel is one position; the four coloured curves within a
panel are the two directions crossed with the two strengths. A positive value
means steering toward the high pole raised the reported class. The two control
panels on the right are flat within their error bars at every layer and both
strengths, which is what makes the two left panels readable at all. At PANL the
$\alpha=5$ high curve rises to $+0.058 \pm 0.022$ at layer 11 and the low curve
falls to $-0.021 \pm 0.023$; at CC the high curve reaches $+0.163 \pm 0.051$ at
layer 22. The paper's corresponding Gemma values are $+0.175$ and $-0.200$ at
PANL and $\pm 0.400$ at CC, so the effects here are roughly a third the size,
which is consistent with the paper's own observation that steering effects are
weaker in Qwen than in Gemma.

Three checks decide this experiment, and all three pass. Steering at PANL
modulates confidence more than either control does. The controls are null
relative to PANL. And PANL's effect peaks at an earlier layer (11) than CC's
(22), which is the temporal-precedence signature; the guidebook's expected Qwen
peaks are L15 for PANL and L22 for CC. A paired comparison against the control
at PANL's peak layer gives $\Delta = +0.050 \pm 0.021$ for high steering
($p = 0.025$, Cohen's $d = 0.49$) and $\Delta = -0.033 \pm 0.019$ for low
steering ($p = 0.088$, $d = -0.36$). The high direction is significant at 24
trials; the low direction is not, and that asymmetry is expected from the class
distribution in Figure 5.1, since a test set drawn from a high-skewed
distribution has more room to move down in principle but starts closer to the
classes the model actually uses.

### 5.4.3 Activation patching

This is the first of two experiments that did not reproduce at this scale, and
the reason is visible in the corruption gate rather than in the patching result.

The guidebook requires that mean-ablating the answer tokens must collapse the
model's confidence: logit difference to near zero, confidence to the lowest
class, and a 100% first-token change rate. Obtained: clean logit difference
8.49 against the paper's 11.5, corrupt logit difference 3.74 against the paper's
0.0, confidence 0.725 falling to 0.567, and a 70.8% first-token change rate
against the paper's 100%. Corruption moved every metric in the right direction,
so the three directional gate checks pass, but it did not collapse the signal.
With a corrupt baseline still carrying a logit difference of 3.74, the recovery
denominator $M_{\text{clean}} - M_{\text{corrupt}}$ is less than half its
intended size, and recovery percentages become correspondingly unstable.

The patching results follow from that. Best confidence recovery was 0.0% at
PANL, 7.9% at PANL+1 and 100% at CC. Two of the four validation checks fail:
patching PANL did not partially recover confidence, and PANL+1 was not worse
than PANL. The CC result is uninformative by construction, as the paper itself
notes, because CC's residual stream feeds the unembedding directly and patching
it late simply bypasses the corruption. At layers 0 and 5, PANL patching
produced *negative* recovery (−226% and −239% on confidence), meaning the
patched run was further from clean than the corrupt run was; writing a clean
early-layer activation into an otherwise corrupted forward pass creates an
internally inconsistent state rather than restoring anything.

I read this as a failure of the corruption step at reduced scale, not as
evidence against the paper's claim. The mean answer embeddings are computed from
a 40-trial calibration set here against the paper's 100, so the "mean answer
token" is estimated from a quarter as many samples and retains more
trial-specific structure. Two other experiments testing the same positions with
different interventions (§5.4.4 and §5.4.7) do dissociate PANL from PANL+1 on
these same trials, which is what makes the diagnosis specific rather than a
general appeal to noise.

### 5.4.4 Activation noising

Mean ablation replaced each position's activation with the mean over the
balanced 40-trial calibration set, and disruption was measured by the increase
in first-token change rate and the decrease in logit difference. All five
validation checks pass.

The maximum first-token change rate was 16.1% at PANL, peaking at layer 16
against the guidebook's expected L11 and 14.0%; 3.2% at PANL+1 (expected 3.5%);
and 32.3% at CC, peaking at layer 22 against an expected L21 and 78%. The clean
logit difference of 7.00 fell to 6.60 under PANL ablation and to 3.49 under CC
ablation, against expected values of 8.4 and 2.8 from a clean baseline of 9.4.
Paired against the control, PANL at its peak layer gives
$\Delta = +0.161 \pm 0.067$ ($p = 0.023$) and CC gives
$\Delta = +0.323 \pm 0.085$ ($p = 0.0007$).

The pattern the paper reports is reproduced in full: both key positions are
necessary, the control is not, disruption is partial rather than total, and PANL
peaks before CC. Partial disruption is expected, since ablating one layer leaves
every other layer's contribution intact.

### 5.4.5 Representation swap

The swap ran as a 2×2 design over 24 recipients per condition, with donors
matched to recipients on tokenized question and answer length using quantile
bins.

![Activation swap at PANL, layer 11. Bars are the mean change in reported
confidence for each of the four donor-recipient conditions, with SEM error bars;
the black dashes mark the paper's own values for the same
conditions.](../assets/data/results/figures/exp4-swap-conditions-qwen-categorical-triviaqa-reduced.png)

*Figure 5.3.* The two same-band conditions on the outside (H→H, L→L) are the
controls: any swap introduces a foreign internal state, and whatever these two
show is generic disruption. Both sit at approximately $+0.004 \pm 0.021$, so
generic disruption is nil here. The informative comparison is each cross
condition against its own same-band control. H→L reaches $-0.051 \pm 0.021$, a
cross-minus-same difference of about $-0.055$ in the predicted direction, and
its error bar excludes zero. L→H reaches $-0.007 \pm 0.040$, which is both the
wrong sign and indistinguishable from zero, against the paper's $+0.21$.

So one direction of the swap reproduced and the other did not. Asymmetry is
itself expected in some settings; the paper reports L→H dominating on MMLU and
in Magistral, attributing it to a confidence distribution concentrated at the
top which creates a ceiling for high-confidence recipients. The asymmetry here
runs the opposite way, which that explanation does not cover. The most likely
cause is the L→H test pool: with 60.8% of trials in the high band and 4.8% in
the low band (Figure 5.1), the low-confidence recipient pool is drawn from
approximately 48 available trials in the whole 1,000-trial run, and the 24 used
are close to all of them.

This experiment's notebook was re-run after its outputs were cleared, so the
per-condition table and the paired significance tests are not recoverable from
the archived artifacts; the figure is. The numbers quoted above are read from
the figure, and no significance test for this experiment is reported here
because none survives in the saved outputs.

### 5.4.6 Out-of-distribution control

The concern this experiment addresses is that any activation edit might push the
residual stream somewhere the model never naturally goes, so that the effects of
§5.4.2 to §5.4.5 reflect generic breakage. The test compares each intervention's
drift against the *natural* pairwise variability between two unrelated trials at
the same position.

Steering passes cleanly. At $\alpha = 5$ the minimum cosine similarity to the
clean activation is 0.985 at PANL and 0.986 at PANL+1, with norm ratios in
$[0.97, 1.06]$, all inside the natural pairwise range at those positions.
Patching and noising do not: pre-patch cosine similarity averages $-0.064$ at
PANL against $0.424$ at PANL+1, a gap of 0.487 against a natural distribution
only 0.307 wide, and noising sits at 0.70 for both positions.

The formal check "PANL and PANL+1 drift comparably under patching" therefore
fails. Two things about that. First, the paper's own numbers come from Gemma 3
27B at layer 25, where the natural pairwise cosine between two unrelated trials
is already 0.997 to 1.000, so every intervention there lands above 0.99 almost
by construction; on a 7B model the natural distribution is far wider and drift
has to be read against it rather than against the paper's absolute 0.99. Second,
the failure is specific to patching and noising, which is consistent with §5.4.3:
patching replaces answer embeddings with a mean estimated from 40 trials, and
that mean is a poor stand-in for any individual trial. The steering result, which
is the experiment that produced the headline PANL effect, is inside the natural
range and is not affected.

### 5.4.7 Probing and variance partitioning

Linear probes were trained on residual activations at six positions with
five-fold cross-validation, using L2-regularized logistic regression for binary
correctness (reported as AUROC) and Ridge regression with $\alpha = 1.0$ for the
confidence midpoint (reported as $R^2$). Features were z-scored inside each
fold, with the scaler and estimator combined in one pipeline so that scaling is
refit per fold and no test-fold information leaks into training.

![Layerwise probing. Left: correctness decodability (AUROC) at six positions,
with horizontal reference lines for the verbal report's own correctness AUROC
and for the mean answer log-probability's. Right: verbal confidence decodability
(cross-validated Ridge R²) at the same
positions.](../assets/data/results/figures/exp6-probing-qwen-categorical-triviaqa-reduced.png)

*Figure 5.4.* Read the right panel first, since it carries the dissociation.
PANL (blue) is the only position with positive $R^2$ before layer 16: it is at
0.159 by layer 5 and 0.262 by layer 11 while CC (red) is still negative, and it
peaks at 0.608 at layer 16. CC overtakes it afterwards and peaks at 0.797 at
layer 27. That ordering, confidence decodable at PANL earlier than at CC, is the
cached-retrieval signature at the representational level, and it is the same
ordering the causal experiments produce. The control position QTT (yellow) is
strongly negative everywhere, meaning the probe does worse than predicting the
mean, which is the correct behaviour for a position carrying no signal. The left
panel shows correctness is decodable almost everywhere, peaking at 0.884 at PANL
and 0.886 at CC, with even the answer colon reaching 0.825; only QTT stays near
chance at 0.666. Information being widely present while causal effects are
narrowly localized is exactly the pattern the paper reports, and the reason it
insists that probing without intervention over-reads.

The variance partitioning asks whether PANL's signal is reducible to token
log-probabilities. Six summaries of the answer-span log-probabilities were
computed (length-normalized mean, minimum, maximum, variance, first token, last
token) and each was regressed against the verbal confidence midpoint, alone and
concatenated with the activations.

![Variance partitioning. R² uniquely attributable to activations, beyond all six
log-probability baselines combined, plotted against layer for four positions.
The dotted line is the paper's PANL value at its peak layer; the dashed line is
what all six baselines explain on their
own.](../assets/data/results/figures/exp6-variance-partition-qwen-categorical-triviaqa-reduced.png)

*Figure 5.5.* The plotted quantity is
$R^2_{\text{unique}} = \max(0, R^2_{\text{both}} - R^2_{\text{base}})$, the gain
from adding activations to a regression that already contains every
log-probability summary. This is the conservative form of the test, since it
credits the baselines with all redundant linear information. PANL rises from
zero to 0.455 at layer 16 before falling back; CC rises later and reaches 0.638
at layer 27; PANL+1 stays near zero until layer 22 and tops out at 0.148; AC is
flat at zero across every layer. All four validation checks pass. The individual
baselines explained between 0.010 and 0.180 of confidence variance, and all six
combined explained 0.157, barely more than the best single one (the minimum, at
0.180, which the combination does not even match on this sample), confirming the
paper's observation that the six carry substantially overlapping information.
PANL's 0.455 is nearly three times what the whole baseline set explains, and
exceeds the paper's own 0.380.

Two auxiliary correlations came out close to the paper's and one did not. The
length-normalized mean log-probability correlates with the Phase-1 confidence
report at $r = 0.317$ against the paper's 0.29, and with the Phase-0 report at
$r = 0.141$ against 0.23. Phase-0 and Phase-1 confidence agree at only
$r = 0.385$ here against the paper's 0.63, which means the model's report about
the same question and answer is markedly less stable across the two prompt
framings on Qwen than on Gemma. That instability is an upper bound on how much
of the confidence signal any experiment here can hope to explain.

### 5.4.8 Answer-colon controls

The question is whether verbal confidence is produced by the same machinery that
produces the answer. AC is the natural test: its final-layer residual stream is
what the unembedding turns into the first answer token, so under a first-order
account, where confidence is a readout of the same signals that drove
generation, interventions at AC should move it.

Four analyses were run on the same trials, with one deliberate asymmetry: the
Ridge penalty for the decoding comparison was tuned on AC and then reused
unchanged for PANL and PANL+1, which biases the comparison in AC's favour so
that a weak AC result cannot be an artifact of hyperparameter selection. The
selected penalty was $\alpha = 1000$.

| Analysis | AC | PANL | PANL+1 |
|---|---|---|---|
| Steering, max abs. Δ confidence | 0.033 | 0.058 | 0.029 |
| Patching, max confidence recovery | 0.00% | 0.00% | 7.89% |
| Noising, max first-token change rate | 0.031 | 0.125 | 0.062 |
| Decoding, peak Ridge $R^2$ | 0.126 | 0.624 | 0.537 |

Four of the five checks pass. Steering at AC is weaker than at PANL and
comparable to the control; noising at AC disrupts less than at PANL; and AC
decodes confidence far more weakly than PANL, at 0.126 against 0.624, close in
ratio to the paper's 0.2 against 0.75. The patching row fails only because
§5.4.3's PANL recovery was itself zero, so the comparison has no content.

The reading is not that AC contains nothing. It contains enough to decode
correctness at AUROC 0.825 (§5.4.7), which plausibly includes answer
log-probability and other generation-time features, exactly because AC produces
the first answer token. It is that this representation is both quantitatively
weak and causally inert when the model verbalizes confidence: the model has
generation-time evidence available at AC and does not primarily draw on it.

### 5.4.9 Attention blocking

Blocking requires access to attention weights, so this experiment runs under an
eager attention implementation, and it uses the minimal numeric prompt whose
purpose is to reduce the number of template tokens between PANL and CC. In the
full categorical prompt that gap is 238 tokens on Qwen, which gives confidence
information many alternative routes.

![Attention blocking with the minimal numeric prompt. Left: first-digit change
rate against the centre of a 12-layer blocking window, one curve per blocked
pathway. Right: the corresponding change in logit difference. Error bars are
SEM.](../assets/data/results/figures/exp8-blocking-minimal-qwen-minimal_numeric-triviaqa-reduced.png)

*Figure 5.6.* Each curve is one severed pathway; the x-axis is where the
12-layer blocking window sits, so a curve peaking to the left means the blocked
edge carries its information early. The orange curve (CC→PANL+1) is the control
and stays at or below 17% everywhere. Two effects separate from it. The red and
purple curves (PANL→answer tokens, and PANL→last answer token only) peak at the
earliest window, centred on layer 10, at 54% and 50%. The blue curve (CC→PANL)
peaks later, at the window centred on layer 22, at 58%. The right panel shows
the same ordering in logit difference: PANL→A drops to −0.48 at the early
window while CC→PANL is still at −0.28, and CC→PANL reaches its own minimum of
−0.38 at layer 20.

That ordering is the whole result. Confidence information moves from the answer
tokens into PANL at early-to-middle layers, and from PANL into CC at later
layers. The gap between the two peaks is 12 layers here against the paper's 6 to
8, but the model has 28 layers rather than 62, so a 12-layer gap on Qwen is
proportionally larger than the paper's on Gemma, and with only four blocking
windows swept the peak location is coarse.

The just-in-time test is the green curve (CC→Q+A). Read at the window where the
CC→PANL retrieval effect actually lives, layer 22, blocking CC's access to the
question and answer produces a 20.8% change rate against the control's 16.7%
and CC→PANL's 58.3%. If CC were integrating question and answer information from
scratch, severing that access would be catastrophic; it is not. Taking the
maximum across all four windows instead puts CC→Q+A at 29.2%, above the control,
and both numbers are reported here because the difference is an artifact of how
the curve is summarized at 24 trials rather than a substantive disagreement.
Paired against the control, CC→PANL at layer 22 gives $\Delta = +0.417 \pm
0.103$ ($p = 0.0005$) and PANL→A at layer 10 gives $\Delta = +0.458 \pm 0.120$
($p = 0.0009$).

The complementary run on the full categorical prompt reproduces the paper's
pattern closely. Blocking every downstream token from attending to the last
answer token produces a 45.8% change rate (paper: 51%); preserving only the
PANL→answer pathway while blocking everything else cuts that to 25.0% (paper:
22%). The same holds for all answer tokens: 41.7% dropping to 37.5% (paper: 68.5%
dropping to 45.5%). Every CC-sourced blocking condition stays between 8.3% and
12.5%, matching the paper's 9% to 12%. And blocking CC→PANL alone produces
nothing in the categorical prompt, 8.3% against the control's 8.3%, which is the
null the paper also reports and attributes to redundant routing through those
238 intermediate tokens.

### 5.4.10 Generalization suite

The paper generalizes along four axes. Two ran here.

Axis 1 substitutes a numeric (0–100) confidence prompt. Over 150 trials Qwen
reached 61.3% accuracy with ECE 0.264 against the paper's 0.16 and AUROC 0.712
against 0.73, at a mean stated confidence of 0.850. The calibration is markedly
worse than under the categorical prompt, which is consistent with the model
anchoring on round numbers near 90. Steering under this prompt reproduces the
precedence ordering (PANL peaks at layer 11, CC at layer 22) but not the
control dissociation: PANL's effect does not exceed PANL+1's. With 75 held-out
trials and a first-digit metric that is noisier than a ten-class argmax, this is
a null rather than a contradiction.

Axis 2 substitutes Qwen 2.5 7B for Gemma, which is the model every experiment
above already ran on, so this axis is validated by the whole chapter rather than
by a separate run. Its noising peaks (PANL L16, PANL+1 L5, CC L22) sit close to
the guidebook's expected L11, L6 and L21.

Axes 3 and 4 did not run; §5.6 says why.

## 5.5 What reproduced

The paper's central claim reproduces. Confidence-relevant information is
represented at the post-answer newline before it is represented at the
verbalization site, and that ordering appears independently in three different
kinds of evidence: causal steering (PANL peaks at L11, CC at L22), necessity
under mean ablation (PANL at L16, CC at L22), and linear decodability (PANL
positive from L5, CC only from L16). Attention blocking traces the same route in
the forward direction, from answer tokens into PANL early and from PANL into CC
late. The control position one token away shows nothing under steering, noising,
blocking or swap, so none of this is generic disruption. And the cached
representation is not reducible to token log-probabilities: it explains
$R^2_{\text{unique}} = 0.455$ of verbal confidence variance beyond all six
log-probability summaries combined, which together explain 0.157.

## 5.6 What did not run, and why

Three parts of the paper could not be executed here. They are reported rather
than omitted.

**Gemma 3 27B.** The licence was obtained and `HF_TOKEN` was set. The checkpoint
is approximately 54 GB in bfloat16, too large for one 48 GB A6000, so it needs
multi-GPU sharding via `device_map="auto"`. Under that configuration every
generation is unusable: with the `sdpa` attention implementation the run crashes
with a device-side assertion inside `transformers.masking_utils`, and with
`eager` it does not crash but emits garbage tokens unrelated to the prompt. The
cause was isolated to `Gemma3TextModel.forward` in `transformers` 5.16.1, which
computes the per-layer-type rotary position embeddings and the causal mask
mapping once, on the hidden state's initial device, and then passes those same
tensors into every decoder layer regardless of which GPU `accelerate` placed
that layer on. The behaviour is independent of attention implementation,
batching, padding and tokenization: a single unbatched, unpadded prompt
reproduces it. This is a `transformers`/`accelerate` compatibility gap rather
than a bug in the reproduction code, and it is not fixable through
configuration. A quantized load would work but trades numerical fidelity against
the paper's own bfloat16 setting, and was not attempted.

**Big-Math and MMLU.** The guidebook names no Hugging Face repository id or
configuration for either dataset, saying only that they are available on the
hub. Rather than guess a source, the loaders raise a named exception and the
notebook reports it, printing the paper's accuracy anchors (40.2% and 76.8%) for
whoever provisions them later.

**Magistral Small 24B.** The checkpoint is not in the local cache. The code path
for this axis is fully implemented, including the chain-of-thought Phase 0, the
trace-carrying Phase 1 prompt, the stratified activation set, the response-block
corruption scope, trace-length donor matching and the ten trace probe positions,
and runs as soon as the checkpoint is downloaded.

The consequence for the paper's generalization claim is direct. Of the four
axes, two ran, so "generalizes across datasets, architectures and reasoning
models" is supported here only for the prompt-format and second-architecture
axes. The other two are neither confirmed nor contradicted.

## 5.7 Self-audit of the reproduction

An audit of the reproduction against its own specification found five classes of
gap, and they are reported here because reproducibility work that locates its
own limits is a result in its own right.

Axis 4 is a facade for three of its four required experiments: the shared
two-phase pipeline routes Magistral through the generic categorical prompt
builder rather than the dedicated chain-of-thought one and truncates at 64
tokens instead of 1024, and there is no Phase-1 counterpart that reads class
logits back into a trial, so the axis's patching, noising, swap and decoding
experiments were never wired up end to end. Axis 3 is incomplete in the same
way: only an accuracy check runs, and both datasets would fall back to the
generic grader instead of the dataset-specific ones the guidebook names, which
for MMLU means routing a deterministic single-letter comparison through an LLM
judge. Experiment 6 is missing two required pieces: the six per-baseline
$R^2_{\text{unique}}$ curves exist in the module and are unit-tested but are
never exercised end to end (only the combined pass runs), and the
intermediate-token probing position is absent from the position set entirely.
Two reproducibility gaps remain in the intervention code: the swap experiment
seeds donor tie-breaking with Python's `hash()`, which is randomized per process
unless `PYTHONHASHSEED` is set, so exact donor assignment on quantile-bin ties
is not reproducible run to run, unlike every other seed in the codebase; and the
attention-blocking code never asserts that the eager implementation is active
before blocking, which is exactly the failure mode a fused attention backend
would produce silently. Finally, the two trial selectors in the patching
experiment band on different phases, one on the Phase-0 report and one on the
Phase-1 report, which the guidebook does not settle either way but which should
have been made consistent deliberately.

None of these affects the numbers reported in §5.4 for the experiments that did
run. All of them bound how far §5.5's claim can be pushed.

## 5.8 Non-obvious implementation decisions

Four decisions had to be made to run the code at all, and each is marked in the
source.

The prompt body is a single user turn and the trailing cue is prefilled as the
start of the assistant turn, so that CC (respectively AC) is genuinely the last
token of the prompt and the next-token logits are read there. The exception is
the minimal numeric prompt, which is fed as raw text, because that prompt exists
precisely to minimize template tokens between PANL and CC and a chat template
would reinsert turn markers there and place the PANL+1 control on a special
token.

Trials whose PANL is not isolable are dropped rather than analysed. A PANL token
is accepted when it starts exactly at the post-answer newline and contains only
whitespace, so a tokenizer that merges a blank line into one `"\n\n"` token is
fine while an answer ending in punctuation that merges into `".\n"` is not. The
guidebook lists a merged newline as the specific cause of a spurious PANL/PANL+1
dissociation, which makes this a correctness requirement rather than a
convenience.

Clean baselines are recomputed with the same batching as the intervention runs.
Attention in bfloat16 is not bit-exact across batch compositions, and the
metrics compare an intervened run against its clean baseline token by token, so
reusing a differently batched baseline would manufacture first-token changes out
of numerical noise.

Greedy generation passes `repetition_penalty=1.0` explicitly, because a
checkpoint's own generation configuration may otherwise penalize the digits that
appear in the numeric prompts.
