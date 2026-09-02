# 3. Related Work

## 3.1 The anchor paper

Kumaran, Conmy, Barbero, Osindero, Patraucean and Veličković (2026), *How do
LLMs Compute Verbal Confidence?*, is the paper this thesis reproduces and
extends. It asks two questions. The first is *when* verbal confidence is
computed: just in time, at the moment the rating is requested, or automatically
during answer generation and cached for later retrieval. The second is *what*
verbal confidence represents: a readout of token log-probabilities, or a richer
evaluation of how well the answer fits the question.

Their evidence for cached retrieval is convergent across six intervention
types. Steering vectors injected at PANL modulate the reported class, with
efficacy peaking at layers 21–25 in Gemma 3 27B, while the same vectors at CC
peak later, at layers 30–35. Patching PANL after answer corruption partially
restores the original report, again peaking earlier than CC. Mean ablation at
PANL disrupts the report, and the control position PANL+1 shows nothing under
any of the three. Cross-confidence representation swaps at PANL shift the
recipient's report in the donor's direction beyond what same-confidence swaps
produce. Attention blocking traces the pathway: blocking CC's access to the
question and answer tokens produces effects indistinguishable from control,
which rules out just-in-time computation, while blocking CC's access to PANL
disrupts the report at layers 30–36 and blocking PANL's access to the answer
tokens disrupts it earlier, at layers 22–28. Finally, linear probes show that
correctness and confidence become decodable at PANL before CC, and variance
partitioning shows PANL activations explain $R^2_{\text{unique}} = 0.38$ of
verbal confidence variance beyond a combined six-summary log-probability
baseline that itself explains only $R^2_{\mathrm{CV}} = 0.10$.

The paper positions cached retrieval as the dominant rather than the sole
pathway, on the grounds that model behaviours generally arise from overlapping
heuristics rather than single circuits (Lindsey et al., 2025; Ameisen et al.,
2025). It generalizes the result across four axes: a numeric prompt format, a
second architecture (Qwen 2.5 7B), two further datasets, and a reasoning model
with an extended chain-of-thought trace.

## 3.2 Uncertainty quantification and verbalized confidence

The anchor paper sits inside a literature on extracting uncertainty estimates
from LLMs. Token likelihoods yield well-calibrated confidences for
multiple-choice and yes/no formats (Kadavath et al., 2022), and sampling-based
consistency methods estimate uncertainty by measuring agreement across repeated
generations (Tian et al., 2023). Semantic entropy refines the sampling approach
by clustering generations that mean the same thing before measuring their
spread, and detects hallucinations well enough to be reported in *Nature*
(Farquhar et al., 2024).

Both families require access the deployed setting usually does not grant. Most
deployed models are black boxes that expose neither token-level probabilities
nor cheap repeated sampling, which is what motivated *verbalized* confidence:
prompting the model to state its confidence as a number or a class name (Xiong
et al., 2023; Yoon et al., 2025). Xiong et al. (2023) benchmark verbalized
confidence across five models and five datasets and find systematic
overconfidence that improves with model capability. Groot (2024) reports the
same picture from an independent replication across four LLMs and two vision
language models: high calibration error and overconfidence in nearly every
condition. Verbalized confidence is therefore widely used and known to be
poorly calibrated, and until the anchor paper nobody had asked where in the
network it comes from.

## 3.3 Probing and self-verification of hidden states

A parallel line of work shows that LLM activations carry more information about
output quality than the outputs themselves reveal. Classifiers trained on hidden
states separate true from false statements more accurately than
probability-based methods (Azaria & Mitchell, 2023; Burns et al., 2022; Bürger
et al., 2024). Zhang et al. (2025) probe reasoning models' hidden states and
recover intermediate-answer correctness accurately enough to use the probe as
an early-exit verifier, cutting inference tokens by 24%. Chen et al. (2026)
formalize query-level uncertainty and show that a training-free "internal
confidence" signal, aggregated across layers and tokens, beats several
baselines while costing less to compute.

These results establish that the information exists internally. They do not
establish that the model's own verbal report is drawing on it, which is the gap
the anchor paper's causal interventions close, and which is why probing alone
is treated there and here as insufficient without complementary intervention
(Elazar et al., 2021).

## 3.4 Mechanistic interpretability methods

The intervention battery is standard equipment. Activation steering rests on
the finding that abstract properties are encoded as approximately linear
directions in activation space (Turner et al., 2023), and has been applied to
instruction following (Stolfo et al., 2024a) and persona traits (Panickssery et
al., 2023). Activation patching under the corrupt-then-restore paradigm comes
from Meng et al. (2022), with best practices systematized by Zhang & Nanda
(2023) and Heimersheim & Nanda (2024). Interchange intervention, the formal
basis of the swap experiment, is due to Geiger et al. (2021). Attention
knockout comes from Geva et al. (2023), whose result is the closest structural
precedent for the anchor paper: during factual recall, attributes are
aggregated at the last subject token in early layers and retrieved later at the
prediction site, rather than being computed at the prediction site from
scratch. Stolfo et al. (2024b) identify final-layer neurons that regulate
output confidence by modulating LayerNorm scale, which is a claim about the
output end of the pipeline rather than about where the confidence signal is
formed.

## 3.5 Ontology in knowledge representation

Benzon (1987) argues that categorizing entities by kind (object, plant, animal,
human) reflects an ontological structure representable as inheritance trees
orthogonal to conventional `isa` trees, and distinguishes paradigmatic
transitions within a category from ontological transitions across categories.
Benzon (2023) applies the same apparatus to ChatGPT, probing concrete versus
abstract categorization and using twenty questions as a way of testing whether
the model can navigate a category hierarchy, and reports better performance on
abstract than on concrete targets. Related essays argue that LLMs encode rich
conceptual ontologies that govern surface generation (Benzon, 2025).

This is a different sense of "ontology" from the one used in formal ontology
engineering, where the task is to extract a machine-readable domain ontology
from a model. Benzon's question is about what kinds of things a system's
representations treat the world as containing, which is the sense this thesis
needs, and the reason his vocabulary is imported rather than that of the
knowledge-engineering literature.

The broader philosophical background is Dennett's treatment of belief
attribution. On the intentional stance, attributing beliefs to a system is a
predictive strategy whose warrant is that it works, and the patterns it picks
out are real without being metaphysically basic (Dennett, 1987, 1991). Chapter
8 uses this to state what the third of the three readings in §1.2 actually
commits one to.

## 3.6 Epistemic emotions

The choice of which constructs to generalize to is not arbitrary. Cognitive
science distinguishes epistemic emotions, which arise from appraisals of how
new information fits existing knowledge, from basic affect. Surprise, curiosity
and confusion form the core of this family, and Vogl et al. (2019) show across
three experiments that they arise most strongly from high-confidence errors,
where incoming information conflicts with a confidently held belief, and that
they drive subsequent knowledge exploration. Pekrun and colleagues' Epistemically
Related Emotion Scales measure them as a distinct construct family (Pekrun et
al., 2017).

This motivates restricting the extension to knowledge-appraisal constructs
rather than sampling an affect battery. The constructs implemented in Chapter 6
(commitment, nuance, challenge, variety, impurity) are all appraisals of the
model's own epistemic situation with respect to its answer, which is the same
family confidence belongs to.

## 3.7 Gap statement

Nobody has tested whether the cache-then-verbalize architecture is specific to
confidence. The anchor paper generalizes across prompt format, dataset, model
architecture and reasoning mode, and every one of those axes holds the
construct fixed. That is a robustness argument, and a good one, but it leaves
the question of §1.2 untouched: is confidence special, or is any self-report
the prompt asks for computed the same way? Chapters 6 and 7 test exactly that.
