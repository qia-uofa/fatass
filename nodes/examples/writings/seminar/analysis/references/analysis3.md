# Analysis: Enea Naco on Benzon, "Ontology in Knowledge Representation" (1985)

## Confirming the same-author link

Reference paper 3 (`references/paper3.pdf`) is titled "Ontology in Knowledge
Representation," by William L. Benzon, copyright line "Copyright 1985, 1987
by William L. Benzon," with contents running Introduction: Salt and Sodium
Chloride / Ontology and Assignment / Paradigmatic and Ontological Transition
/ CIMWorld / Multiple Ontologies / References. This is, beyond doubt, the
same document our subject paper's Appendix lists as:

> William Benzon, *Ontology in Knowledge Representation in CIM*. Center for
> Manufacturing Productivity and Technology Transfer, Rensselaer Polytechnic
> Institute. Report No. CIMNW85TR034, January 1985 ... Given ontological
> structure we can define paradigmatic transitions, such as that from
> caterpillar to butterfly, and ontological transitions, such as that from
> living to dead.

Every distinctive element named in the Appendix abstract — the
object/plant/animal/human inheritance trees, their orthogonality to "isa"
trees, the caterpillar→butterfly and living→dead examples, the CIM
world — is present in the body of paper3. So this reference set is not an
independent secondary source: it is Benzon's own 1985 formal apparatus,
self-cited thirty-eight years later in the paper we are seminaring on. Enea
Naco's presentation states this explicitly on slide 1 ("William L. Benzon
(1985)"), correctly. That means nearly every point below can be read two
ways at once: as this student's reaction to the 1985 machinery on its own
terms, and as a reaction to the *same* machinery Benzon was still quietly
running underneath his 2023 ChatGPT experiments — making this presentation,
structurally, a commentary on the theoretical skeleton of our subject paper.

One striking piece of direct evidence for that continuity: the salt/NaCl
example that opens paper3 ("We all know that salt and sodium chloride are,
physically, pretty much the same. Conceptually they are very different...
Salt is thus rather adequately defined in terms of sensory perceptions")
reappears almost verbatim as the organizing example of the subject paper's
introduction and its "From Salt and NaCl to the Great Chain" section
("salt," conceptually concrete, vs. "NaCl," conceptually abstract). Likewise
the Morning-Star/Evening-Star example that paper3 uses in passing ("Logicians
have long been fond of a homily about the Morning Star and the Evening
Star, which are not stars at all, but the planet Venus") is the exact
example Benzon runs past ChatGPT in the subject paper's dialogue transcript.
Benzon is not just citing his old paper; he is re-running its illustrative
examples on a language model that did not exist when he wrote them.

## Slides 2-3: the intro hook and "the problem"

Naco opens by asking how many people play more than one role in their life,
and frames the core difficulty as: single-hierarchy classification breaks
when an entity (a person) plays incompatible roles. This is a faithful
restatement of paper3's own framing move — Benzon introduces exactly this
problem via Winograd's point about "inheritance from multiple
superordinates" becoming acute for social structure (student, teacher,
mother, son, waitress, judge as varieties of "person").

The subject paper does not test multiple-role inheritance directly (its 20
Questions targets are single concepts, not social roles), but it opens with
the cognate problem of what *can* be coherently predicated of a category —
Chomsky's "colorless green ideas sleep furiously" and ChatGPT's refusal to
tell a story about a "colorless green idea" because ideas "do not have any
physical properties." Both papers are, at bottom, about which attributes a
representational structure licenses an entity to inherit; Naco's framing
picks the social-role version of the same problem the subject paper's
opening picks the perceptual-attribute version of.

## Slides 4-5: "Meet George" and the contradiction

The George example (teacher who wields authority, son who submits to it,
producing a contradiction if both roles are inherited into one hierarchy)
is lifted directly from paper3's own running example: "Consider George, who
is both a teacher and a son. Teachers are supposed to wield authority while
sons are supposed to submit to it... George is thus both submissive and
authoritative, which doesn't quite make sense." Naco's slides 4-5 reproduce
this almost exactly, correctly identifying it as a genuine inheritance
contradiction, not a strawman.

This has no direct test case in the subject paper — Benzon never asks
ChatGPT to reconcile conflicting social roles — but it does bear on the
subject paper's closing worry about ChatGPT's reasoning limits: LLMs "have
problems with some commonsense reasoning, and various kinds of 'tight'
logical reasoning." The George contradiction is exactly the kind of
structured, formally-representable puzzle (not brute-force factual recall)
where the subject paper's own hedging about ChatGPT's reasoning depth would
predict trouble; the subject paper just never poses it.

## Slide 6: the two-trees fix — and why this is the subject paper's Great Chain

This is the strongest, most underexploited connection in the whole
presentation, and the presentation doesn't flag it. Naco summarizes
Benzon's fix as two independent structures: a **paradigmatic tree** ("is a"
hierarchy, e.g. dog → beast → animal, properties flow downward) and an
**assignment tree** ("what kind of being something is," e.g. object → plant
→ animal → human → social person, properties flow upward — "if animals can
feel hungry, humans can too").

That assignment-tree chain — object, plant, animal, human, social person —
is, node for node, the Great Chain of Being that the subject paper spends
its entire "From Salt and NaCl to the Great Chain" and "Great Chain" Q&A
sections probing in ChatGPT. Benzon even cross-references this explicitly
in the subject paper itself, footnoting his own "Ontology in Cognition: The
Assignment Relation and the Great Chain of Being" (2018) right where he
introduces the Aristotelian vegetative/sensitive/rational-soul hierarchy —
paper3's assignment tree is the formal machine, and the subject paper's
ChatGPT dialogue ("The Great Chain of Being is a hierarchical structure...
Humans... then animals, plants, minerals...") is that same machine's
informal, folk-encyclopedic echo coming back out of a language model that
was never given the 1985 paper directly. Naco's slide 6 is, without saying
so, restating the exact conceptual object the subject paper spends pages
informally interrogating via chat transcript.

The paradigmatic tree half also has a direct empirical instance in the
subject paper: when Benzon asks for "20 things, anything" repeatedly, the
lists cluster within a "relatively restricted set" of physical objects
(bicycles, coffee mugs, hot air balloons recur) — Benzon reads this as
evidence of gradient/landscape structure, but it is equally an instance of
paradigmatic-tree locality: successive samples stay near each other in a
VAR-arc neighborhood rather than jumping ontological levels. Our own
sidenote's first experiment is an even cleaner case of this: asking for "20
things... start with butterfly, dragonfly..." produces a list that slides
from the rhyme pattern into flying bugs, then general bugs, then flying
mammals, then (after "50 more") general mammals — a textbook walk up a
paradigmatic tree's VAR arcs (insect → flying insect → generalized insect →
flying animal → mammal), exactly the kind of inheritance-hierarchy drift
Figure 2 of paper3 (dog/horse/wombat → beast → animal) is diagramming
formally.

## Slide 7: George fixed — roles assigned, not inherited

Naco's resolution (George is an instance of "human being," with teacher and
son merely *assigned* roles rather than inherited traits, so "his identity
stays the same") again tracks paper3 closely: "By treating the relationship
between George and his various roles as one of assignment this problem is
eliminated, because George inherits nothing from the roles he plays."

There is no direct subject-paper analogue (again, no role-conflict test
there), but it does connect to the subject paper's salt/NaCl point at a
structural level: both are cases where the same underlying entity (George;
NaCl) sits in two different representational structures at once (role
paradigm vs. identity; common-sense ontology vs. scientific ontology)
without those structures needing to be reconciled into one hierarchy. The
assignment relation is the general mechanism; salt/NaCl and George/teacher-
son are two of its instances, one from paper3's own text, one from the
subject paper's.

## Slide 8: food as a functional paradigm

Naco's food example (apples and beef are both food despite no shared
biological parent; food is "not a biological category, it's a functional
one... assigned a role in an eating event") is paper3's own extended
example: food is treated "to be an assignment between some variety of plant
or animal and a particular slot in an eating event," with the
substantive/functional paradigm distinction spelled out explicitly in the
source text.

This connects concretely to the subject paper's own 20-Questions "Apple"
transcript. Playing the game, ChatGPT's route to "apple" runs almost
entirely through the *substantive* (plant/paradigmatic) hierarchy — "Is it
a plant?" → "Is it a type of tree?" → "Is it a deciduous tree?" → "Is it a
fruit-bearing tree?" — before it even reaches "apple," and in the earlier
round it goes through "Is it related to food?" → kitchen → "fruit used in
cooking" → red-colored fruit guesses (strawberry, cherry, raspberry,
pomegranate, blueberry, cranberry, currant...) before landing on apple. In
Benzon's own terms this is ChatGPT groping between exactly the two
paradigms paper3 says are formally distinct — the substantive plant
paradigm (what kind of organism apple is) and the functional food paradigm
(what role apple plays in an eating event) — and doing so inefficiently,
repeating already-eliminated guesses (red currant twice). The Apple game is,
essentially, an unwitting empirical trace of the exact substantive versus
functional paradigm split paper3 formalizes.

## Slides 9-10: paradigmatic vs. ontological transition

This is the presentation's most direct citation of paper3's core
contribution, and it is also the exact distinction the subject paper's
Appendix quotes as paper3's headline result: paradigmatic transitions, such
as caterpillar to butterfly, versus ontological transitions, such as living
to dead. Naco reproduces this with fidelity — caterpillar-to-butterfly as
"form changes, identity stays," a student's expulsion as "the structure
itself changes... a whole layer of what you are... removed" — and correctly
identifies expulsion as an *ontological* (decompositional) transition in
Benzon's sense, paralleling paper3's own discussion of exile ("A
decomposition... to strip them down to mere humanity") and composition
(christening, marriage).

The subject paper does not stage any transition examples of its own (no
"tell me a story about a caterpillar becoming a butterfly" prompt appears),
so there is no direct ChatGPT transcript to compare against here. But the
distinction is thematically present throughout the subject paper's whole
project: the entire point of probing concrete versus abstract and
common-sense versus scientific ontologies (salt versus NaCl) is to locate
where ChatGPT's represented world has real ontological boundaries
(crossable only by composition/decomposition, in paper3's terms) versus
where it merely varies form within one paradigm. Benzon's remark that
ChatGPT "has no access to the physical world, it can't see or touch salt,
much less taste it" is, in paper3's vocabulary, a claim that ChatGPT's
salt-concept and NaCl-concept may not be genuinely different ontological
domains for it at all — since it never performs the assignment-forming acts
(tasting, laboratory measurement) that ground the domains in a human.

## Slide 11: CIMWorld

Naco's object → assembly → mechanism → engine → computer chain, with each
step's defining addition (assembly = object plus connectivity; mechanism =
assembly plus motion; engine = mechanism plus power source; computer =
assembly plus program), is a direct, accurate compression of paper3's
CIMWorld section.

Remarkably, the subject paper contains an almost structurally identical
ChatGPT-generated list that Naco's presentation does not cite but that
belongs here: asked for "a list of mechanical things in increasing order of
complexity," ChatGPT produces simple machines → bicycles → watches →
internal combustion engines → clocks → aircraft engines → industrial robots
→ spacecraft → heavy machinery → particle accelerators. This is a looser,
statistically-generated cousin of paper3's formal object/assembly/
mechanism/engine/computer chain — both are complexity-ordered hierarchies
of mechanical ontology, and Benzon explicitly frames his own list as an
exercise in "mechanistic interpretability," asking how one would go about
finding the gradient that ChatGPT is following — i.e., asking whether
ChatGPT's list tracks anything like the assignment-tree gradient paper3
formalizes 38 years earlier for exactly this domain (mechanical/engineered
objects). Naco's slide 11 is effectively the ground-truth structure the
subject paper's own mechanical-things experiment is informally probing for.

## Slide 12: machining vs. assembly; PhysWorld/InfoWorld

The machining-as-paradigmatic / assembly-as-ontological-transition
distinction, and the PhysWorld/InfoWorld split (with C-machines straddling
both), are both accurate readings of paper3's text: machining moves an
instance from one type to another (paradigmatic), while assembly converts
an imaginary connectivity structure into a real one (ontological).

This has no close analogue in the subject paper's content (no factory or
manufacturing example appears there), so the connection is weaker and more
structural: PhysWorld/InfoWorld is paper3's version of the same
common-sense/scientific ontology split that salt/NaCl exemplifies in both
papers — a physical thing (salt; a machined part) described in two
non-interchangeable representational systems (taste-and-touch common sense;
laboratory chemistry / informatic control representation).

## Slide 13: water vs. H2O

This slide claims water/H2O as a Benzon example and states his generalized
claim that scientific revolutions occur as ontology swaps. Two things are
worth separating here. First, the *general* claim about scientific
revolutions as ontology-swap events is genuinely paper3's own: the
anomalies that have figured so prominently in recent discussions of
scientific revolution (citing Kuhn) betray the inadequacy of an ontology,
and an anomaly occurs when objects undergo actions that do not conserve
ontological structure — so slide 13's closing claim is a fair summary of
paper3's "Multiple Ontologies" section.

Second, the specific water/H2O wording does not actually appear in paper3's
text (its own list of "multiple ontologies" examples is salt/NaCl, Morning
Star/Evening Star, homo sapiens sapiens versus "human race," and the
trained versus untrained auto mechanic's ontology of engines). Water/H2O
is, however, exactly the analogy the subject paper adds on top of the
salt/NaCl case: "The same difference exists between water and H2O and
laughing gas and N2O, and so on for a whole variety of common substances."
So this slide most likely draws — whether knowingly or not — on the
*subject* paper's extension of paper3's example rather than on paper3
directly, which is itself a small but telling data point for how thoroughly
the two papers' framings have merged by the time a third party reads them
together.

## Slide 14: "what the framework gets right"

The claims here (identifies a real multi-role problem; cleanly separates
identity from role; generalizes across domains — social structure,
engineering, science, literature) track paper3's own closing gestures
(Wilensky on story grammars and "human dramatic situations," the extension
from George to food to CIMWorld to scientific revolutions).

The subject paper offers indirect corroboration of the "generalizes across
domains, still relevant" claim: without being fed the 1985 formalism,
ChatGPT independently reproduces Great-Chain-shaped hierarchies (souls,
Great Chain of Being), a common-sense/scientific ontology split
(salt/NaCl), and a complexity-graded object hierarchy (mechanical things) —
three separate instances of paper3's assignment-tree and paradigmatic-tree
structure surfacing from a system trained on decades of text rather than
built from Benzon's explicit representation language. That is reasonably
strong indirect evidence that the ontological structure paper3 formalizes
is a genuine, pervasive feature of how these categories are talked about
(and hence learned by an LLM), not an artifact specific to Benzon's
particular notation.

## Slides 15-16: "they sidestepped it"

Naco's argument — LLMs are fluent on the surface, with "no explicit
ontological structure, only statistical patterns," performing unreliably in
"high sensitivity domains" — is not a claim the subject paper is naive
about; Benzon voices essentially the same worry himself, repeatedly and
explicitly. On salt/NaCl: "While ChatGPT does recognize a difference in
meaning between the two terms, I doubt that that recognition is very deep.
After all, it has no access to the physical world, it can't see or touch
salt, much less taste it... But that's a long way from understanding that
salt and NaCl are embedded in different conceptual systems." On its own
self-report of *not* having discussed ontology when asked directly, Benzon
calls getting from surface fluency to the deeper claim "a much heavier
lift" that he has "got to pause and take a breath" over "after thinking
about these issues for years." Benzon's 2023 hedging is essentially Naco's
verdict already stated in 2023, just from the inside of the experiment
rather than as a retrospective assessment.

The subject paper's own 20-Questions transcripts are, moreover, a direct
empirical illustration of exactly the "sometimes get it right, sometimes
they do not" fragility Naco cites as the concrete symptom of pattern-
matching without structure: ChatGPT forgets its own hint (it is reminded,
and apologizes for missing it), asks a yes/no question phrased as an open
question and has to be corrected by the human player, repeats an
already-rejected guess in the Apple round (guessing "currant" twice), and
miscounts its own question total in the Evolution round. None of these are
failures of world knowledge — ChatGPT clearly "knows" the target
categories — they are failures of maintaining a consistent internal
state/structure across a multi-turn deduction, which is precisely the "no
explicit ontological structure underneath" complaint slide 16 raises
against LLMs generally.

This also bears directly on our own sidenote's second experiment. The
subject paper's headline 20-Questions finding — ChatGPT needs fewer
questions/hints for abstract targets (justice: 7 then 8 questions,
evolution: 8 then 9) than concrete ones (bicycle: 25/10, squid: 29/20,
apple: 31/13) — reads, if taken as evidence of ontological sophistication,
as support against Naco's "sidestepped it" claim (a system with no real
structure "shouldn't" show a principled abstract/concrete asymmetry tied to
category width). Our sidenote directly interrogates this: the working
hypothesis was that this asymmetry is just an A-or-B question favoring the
less-frequent option (fewer abstract words in English, so fewer steps to
narrow down), not evidence of structured understanding — and after
correcting the concrete/abstract sampling distribution to be balanced, the
sidenote's fixed experiment found no significant bias toward either. That
result undercuts the idea that the subject paper's abstract/concrete
asymmetry reflects genuine command of assignment/paradigmatic structure at
all; it may be exactly the kind of surface statistical regularity Naco's
"sidestepped it" argument predicts, dressed up as ontological competence by
an uncontrolled sampling distribution in the original transcripts. In other
words, our sidenote provides independent empirical ammunition for Naco's
skeptical slide 16, sharper than anything paper3 or the subject paper
offers on its own.

## Slide 17: closing takeaway

Naco's final framing — two imperfect workarounds, hardcoded systems
(reliable, inflexible) versus LLMs (flexible, unreliable), neither matching
what Benzon actually proposed — has no single passage in either the subject
paper or the sidenote to map onto directly, since neither of our papers
stages that comparison to symbolic/hardcoded systems. But the underlying
open question (whether LLMs actually understand ontological structure, or
just imitate it convincingly) is the same open question the subject paper
ends on without resolving: Benzon's closing methodological gesture is to
flag how premature it would be to ascribe any statistical significance to
his findings and to ask how many trials, how large a sample of targets, and
what sampling procedure would be needed to make the concrete/abstract
finding trustworthy — the very question our sidenote's second experiment
went on to actually run, and which came back negative. Read together, the
three documents form a small arc: paper3 supplies the formal ontological
machinery (1985); the subject paper informally probes whether an LLM
exhibits that machinery and finds a suggestive but statistically unvetted
asymmetry (2023); our sidenote tightens the experiment and finds the
asymmetry disappears; and Naco's presentation, from the theory side,
independently arrives at the same imitation-not-structure verdict. That
convergence — from a controlled-sampling rerun on one side and a
theory-driven skepticism about LLM internals on the other — is the
strongest connection this presentation makes to our subject paper, even
though Naco never saw the sidenote's result.
