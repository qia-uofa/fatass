# Analysis: Dilekcan Pamir on Benzon's "ChatGPT tells stories, and a note about reverse engineering"

The reference paper (paper2) is a different Benzon working paper than our subject
paper — dated March 3, 2023, eight months before "ChatGPT's Ontological
Landscape." Its method: give ChatGPT a base story ("Princess Aurora," a
five-paragraph fairy tale about a dragon-taming princess), then ask for the same
story with one element changed (usually the protagonist, sometimes the
antagonist — e.g. Aurora → Prince Harry, → Henry the Eloquent, → William the
Lazy, → the robot XP-708-DQ, → a Giant Chocolate Milkshake, → a "colorless green
idea"). Benzon aligns old and new story paragraph-by-paragraph, highlights the
differences, and reads the pattern of what changes and what doesn't as
evidence for two conjectures: (1) ChatGPT generates from a "nested hierarchy of
probability distributions" — story trajectory → segment → sentence → token —
and (2) the magnitude of textual change between old and new story is roughly
proportional to the semantic distance between the old and new
protagonist/antagonist. The reference presentation, by Dilekcan Pamir (Goethe
University Frankfurt, July 2026), reframes this as an instance of a general
"systems perspective" — controlled perturbation of a black-box system to
characterize its behavior — imported from Haralick & Ramesh's computer-vision
"performance characterization" literature, and uses it to motivate the
presenter's own quantitative project (Transformers trained on synthetic binary
Markov sequences, perturbed with bit-flip noise, measured with KL-divergence
and MAE).

What follows tracks each thread the presentation pursues and ties it back to
paper2 on one side and to Benzon's "Ontological Landscape" (our subject paper)
and our own sidenote on the other.

## 1. Recasting Benzon as "black-box perturbation": the Haralick–Ramesh import

Slides 2–4 ("Three complementary worlds," "The paper in one sentence") place
Benzon, Haralick & Ramesh, and the presenter's own project on a shared axis:
same abstract question — "Perturb a system with a known input structure.
Observe what is preserved. Characterise the system's behaviour" — answered with
decreasing rigor from left (Benzon: qualitative, domain-expertise-mediated) to
right (their project: KLD/MAE on synthetic sequences). This framework is not
paper2's own; paper2 never mentions performance characterization or vision
systems. It's an interpretive lens the presenter is laying over Benzon's twelve
experiments, translating "I give ChatGPT a prompt... and instructions to
produce another story like it except for one change" (paper2, p. 2) into "a
controlled input perturbation is applied to a black-box system" (slide 4).

Our subject paper doesn't use this vocabulary either, but its central
experiment — the 20-Questions rounds — is structurally the same move without
the label: six fixed targets, each perturbed by repetition (played twice), with
the "output" (questions-and-hints count) tabulated and read for a pattern
(abstract targets converge faster). Benzon even flags the same evidentiary gap
the Haralick–Ramesh framework exists to close: "it would certainly be premature
to ascribe any statistical significance to these findings... How many times
should we play a given target to establish ChatGPT's behavior for it? ... What
universe are we sampling and how do we choose our samples?" That is Benzon,
inside our own subject paper, independently reaching for something like a
performance-characterization protocol and stopping short of building one — the
same gap presentation2 diagnoses in paper2.

## 2. Translating narrative vocabulary into CS/ML terms — and the line paper2 already drew

Slide 10's glossary ("story trajectory → high-level behavioural regularity,"
"transformation → controlled input perturbation," etc.) ends on: "Benzon
observes output behaviour only — no access to weights, activations, or
attention heads. Systematic, but black-box." This framing treats the
black-box/white-box distinction as an outside CS lens applied to Benzon's
work. But paper2 already draws almost exactly this line itself, in its closing
section "Reverse Engineering ChatGPT": Benzon explicitly distinguishes a
"surface level" (his prompts and ChatGPT's responses — "the transformer
virtual machine is the bottom level"), a "middle level" (patterns of parameter
weights, where he places both his own nested-distribution conjecture and
Anthropic's induction-heads mechanism), and a "bottom level" (the transformer
architecture itself). He states outright that his own experiments "exhibit
surface level behavior" and that the middle level is opaque to him — i.e.
Benzon self-identifies as black-box before the presentation does it for him.
Presentation2's contribution is less a new observation than a relabeling of
Benzon's own three-level coda into the vision-systems white/gray/black-box
vocabulary.

Our subject paper is black-box in exactly the same, undisputed sense (the
Waddington epigenetic-landscape metaphor stands in for the inaccessible middle
level there too, just as the nested-hierarchy conjecture does in paper2 — the
same author reaching for the same kind of geometric placeholder for a
mechanism he can't inspect in both papers). Our sidenote's method is likewise
pure black-box behavioral probing with no claim to mechanism.

## 3. What's preserved, what changes: Aurora → Harry / William the Lazy, and the logic of "assignment"

Slides 8–9 restate two of paper2's twelve experiments as findings: for Aurora →
Harry, "Global trajectory (Disturbance, Celebrate) is preserved. The
protagonist's defining attribute and conflict resolution change... locally, not
uniformly"; for Aurora → William the Lazy, "Disturbance remains unchanged —
independent of the protagonist... epithet acts as a parameterised constraint."
This is a close paraphrase of paper2 itself, which already says of the
Harry/Henry set: "Note also, that as before, the Disturb segment is the same in
both stories. Since the protagonist isn't mentioned in it, there's no need for
any change," and of William the Lazy: "That forced major changes in
Plan/Transit, Enact, and Celebrate... New actors had to be introduced." The
presentation adds no new data here — it distills Benzon's own running
commentary into a clean preserved/changed contrast.

The substantive connection to our subject paper is that this "coherence"
phenomenon — swapping an entity forces recomputation only of the story-slots
that depend on that entity's category, leaving unrelated slots untouched — is
the narrative-level analogue of the "assignment relation" our subject paper's
appendix cites from Benzon's own earlier work: "An object thus may be
considered to be an assignment between a form and a substance, and living being
(plant) an assignment between an object and a vegetative soul... Inheritance
goes up such a hierarchy." Paper2's Enact segment changing (sword-fighting vs.
singing) because Harry inherits "male, martial" attributes while Disturb stays
fixed because it inherits nothing from the protagonist is the same
assignment/inheritance logic the subject paper uses to explain why "Colorless
green ideas sleep furiously" is a category mistake — both are cases of Benzon
treating ChatGPT's outputs as governed by an implicit ontological inheritance
structure, just applied to lexical semantics in one paper and to narrative role
in the other. Our sidenote's list-degradation experiment (butterfly/dragonfly →
flying bugs → general bugs → flying mammals → general mammals) is a looser
version of the same thing — each step substitutes a "protagonist" category and
the properties that get inherited (flight, then just being a small animal)
visibly shift — but the sidenote doesn't develop this as an explicit claim, so
the parallel is suggestive rather than load-bearing.

## 4. The session-history gap, and the mini replication study

Slide 5 flags a "methodological observation": "It is not clearly specified
whether all 12 experiments were conducted in one session or independently —
this may influence reproducibility and interpretation." Slides 14–15 respond
with the presenter's own "Mini Replication Study" (William the Lazy, Henry the
Eloquent, Prince Harry, run under independent-session vs. same-session
conditions), concluding "larger semantic differences tended to produce larger
narrative adaptations — consistent with Benzon's conjecture."

This slightly understates what paper2 itself already does. Benzon runs exactly
this check once, on purpose: experiment 6 regenerates the Aurora → XP-708-DQ
transformation "at the beginning of a session several days after" the first
version specifically to see whether the story changes, and it does — the second
version reframes the whole story as "a galaxy far, far away" rather than a
threatened kingdom. Benzon even attributes the first version's odd choice of
antagonist (a witch, not a robot-appropriate foe) to session-level priming:
"First Aurora the Terrible and then Cruella De Vil had been protagonists...
perhaps their presence (nasty women) in the larger context resulted in witches
being more salient." So Benzon had already identified session-context as a
confound and reported on it narratively; presentation2's "methodological
observation" and mini-replication effectively formalize a concern paper2 raises
about itself in passing.

This is also the strongest connection to our own materials. Our subject paper's
20-Questions protocol runs a first round "on October 15 and 16," then
explicitly "repeated those six targets in a second round on October 17"
specifically as a same-topic reproducibility check, and separately, in the
"list of 20 things" experiment, Benzon reruns the identical prompt three times
— including once after deliberately logging out — asking "I wonder if that
first list is 'rigid' in the sense that ChatGPT would respond the same way given
the same prompt." That is the same independent-vs-same-session comparison
presentation2 runs, done informally, on a different Benzon experiment, in our
subject paper. And it's precisely the sampling/session-control problem our
sidenote's "20 Questions" thread targets directly: the sidenote's "issue" (the
concrete/abstract split in the sample didn't match the real distribution) and
"fix" (sample from a curated, balanced dictionary) is the same kind of
uncontrolled-variable diagnosis, just aimed at target selection rather than
session history.

## 5. Segment-level stability as a synthesis, not a new result

Slide 16's stability table (Donné: low, Disturbance: high, Plan/Action: medium,
Celebrate: medium) reorganizes observations scattered across paper2's twelve
experiment write-ups into one summary. It's a genuine service — paper2 itself
never tabulates this — but it's synthesis of Benzon's qualitative
commentary, not independently measured data (no metric is defined for
"stability" here; it's the same "eyeball the yellow highlighting" method Benzon
names explicitly: "eyeballing the amount of yellow highlighting in the
stories" — a method he attributes, via a footnote, to Mark Liberman's phrase
"inter-ocular trauma," what strikes the eye).

The structural analogue in our subject paper is its own six-target results
table (Bicycle 25 questions/3 hints, Squid 29/6, Justice 7/0, Evolution 8/0,
Apple 31/5, Truth 19/7, repeated in a second round) — a comparable "effort under
perturbation" summary for a different task (guessing rather than
retelling), assembled the same way: post-hoc counting over transcripts rather
than a metric defined in advance.

## 6. The "20 versions of a prototypical story" aside: default attractors

Slide 17 pulls in a third Benzon paper (cited in the presentation's
references as "ChatGPT tells 20 versions of its prototypical story, with a
short note on method") — neither our subject paper nor paper2 itself. Its
reported finding: minimal-prompt ("story") elicitations converge 19-out-of-20
times on the same "exploration-and-return archetype," and "session history
affects protagonist variety." The presenter reads this as evidence of "a
learned narrative prior that emerges consistently without any structural
prompt."

This connects cleanly to our subject paper's own physical-things experiment:
asked three times for "20 things, anything," with no further structure,
ChatGPT returns lists drawn from "a relatively restricted set of all possible
physical objects" — rainbow, bicycle, hot air balloon, and chocolate-chip
cookies recur across independently elicited lists — which Benzon glosses via
the Waddington landscape metaphor: "once the 'ball' enters a valley... it just
rolls downhill." That's the same "default attractor under minimal prompting"
phenomenon the "20 versions" paper reports for stories, just for lists.

It also lines up directly with our own sidenote's first experiment: "give me 20
things, anything, start with butterfly, dragonfly..." — the model rides the
xxx-fly pattern until it's exhausted, then drifts through flying bugs → general
bugs → flying mammals, and under "50 more" collapses into general mammals. That
is the mirror image of the "20 versions" finding: rather than showing that a
minimal prompt converges on one default trajectory, our sidenote shows that a
prompt which starts inside a narrow attractor (the rhyming pattern) decays
outward into progressively broader ones once the narrow one is exhausted — both
are evidence for the same underlying claim, that generation is dominated by a
small set of learned regions rather than sampling the full space the prompt
nominally allows.

## 7. The quantitative analogue: robustness to noise vs. sensitivity to base rates

Slides 18–20 describe the presenter's own separate project — Transformers
trained on binary Markov sequences, corrupted at test time with bit-flip
noise — and report that "the Transformer preserves the training distribution
even under corrupted input... generation from learned behaviour, not noisy
context," in contrast to a k-gram baseline whose error scales with noise. The
"Connecting back to Benzon" slide (20) treats this as quantitative confirmation
of the same story-level finding: "model output behaviour is dominated by
learned organisation, not by the specific input perturbation."

Paper2 has a qualitative version of exactly this: ChatGPT's refusal to make a
"colorless green idea" the protagonist of the Aurora story ("it is not possible
to create a story about a 'colorless green idea' as it does not have any
physical properties or characteristics that can be used in a story," p. 14),
and the parallel refusal when a prompt tried to insert a robot named Gort into
an established fairy-tale-world story ("as Lily's story has not previously
included elements of science fiction... I'm afraid I cannot answer this
question within the context of her story"). In both cases the model resists an
out-of-distribution instruction in favor of its already-established narrative
organization — the same qualitative shape as "the transformer preserves the
training distribution even under corrupted input," just observed through
refusal rather than through an error metric.

Our sidenote's second thread is worth flagging as a partial counter-case rather
than a confirming one. The hypothesis there — that ChatGPT's first 20-Questions
move is reliably "abstract or concrete" because abstract words are rarer in
English, so a binary split toward the rarer class narrows the search faster —
and the finding that "a question asking A or B always favours the less frequent
option," is a claim that model behavior does track fine-grained distributional
structure (word frequency) in the target set, not that it's flat against it.
That's not a contradiction of presentation2's claim (noise-robustness and
base-rate-sensitivity are compatible: the model can both resist corrupted
local input and still be shaped by the statistics of the category it's
sampling from), but it's a reminder that "dominated by learned organisation"
needs unpacking — our sidenote's own fix (resampling from a balanced
concrete/abstract dictionary, which then found "no significant bias towards
either") shows that the specific organisation being preserved is sensitive to
exactly how the input set is constructed, which is the same point paper2's
critique (section 8, below) is ultimately making about story perturbations.

## 8. Making Benzon rigorous: presentation2's fix list vs. our sidenote's fix

Slide 21 proposes turning Benzon's method into a real protocol: generate n
stories per condition rather than one; control model version, temperature,
top-p, and session history; define m perturbation types systematically
(gender, role, personality trait, antagonist); auto-detect segments; use
embeddings to quantify protagonist distance; test statistically whether
perturbation magnitude predicts segment-level change. The framing — "from
observation to characterisation... 'the generated distribution differs
significantly from the reference under a defined metric'" — is a direct
critique of paper2's single-example-per-condition design (each of the twelve
experiments is one run, one story pair, no repetition).

This is the same diagnose-an-uncontrolled-variable-then-formalize-it move our
sidenote makes for a different Benzon experiment: issue ("the distribution of
concrete/discrete in the experiment doesn't match that of the English
dictionary") leads to fix ("sample from a selected dictionary of equal amount of
concrete and abstract words... told the keyword is sampled from here") leads to
result ("no significant bias towards either"). Both critiques target the same
underlying weakness across Benzon's working papers — small, hand-picked,
uncontrolled samples standing in for a claim about the model's general
behavior — and our subject paper itself flags this weakness in its own hand:
Benzon explicitly asks, of the very targets used in the 20-Questions games,
"What universe are we sampling and how do we choose our samples?" without
answering it. Two different student presentations, working from two different
Benzon papers, independently converged on formalizing exactly the gap Benzon
names but leaves open in both papers.

## 9. Closing note

The presentation's own conclusion — "Benzon and Ramesh share a common systems
perspective: perturb, observe what is preserved, characterise behaviour...
different domains, different rigour" — is a fair characterization of the
relationship between all four documents in this comparison, not just the two
the presentation directly discusses. Our subject paper's 20-Questions
experiment, our sidenote's dictionary-balancing fix, paper2's story
perturbations, and presentation2's Markov-sequence noise experiments are all,
at bottom, the same experiment repeated at different levels of formalization:
perturb something ChatGPT is generating, observe what changes and what
persists, and use the answer as indirect evidence about a category structure
(ontological, narrative, or statistical) the model appears to have learned but
that none of these methods can inspect directly.
