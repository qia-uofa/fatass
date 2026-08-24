# Essay skeleton

Nine paragraphs. Target ~1500 words total (task range: 1200–1800). Register:
essayistic, opinionated, blog-post-style — not a formal academic report with
numbered sections (headers below are working titles for planning only; the
generation step should decide for itself whether to keep them as visible
headers or fold them into continuous prose). No paper-by-paper summary
anywhere — every paragraph must argue or evaluate, not narrate contents.
Every reference-paper point must be explicitly tied back to what it shows
about the subject paper's argument, never presented as a parallel mini-summary
of another paper in its own right.

---

## 1. Opening frame: landscape or artifact?

**Role:** Opens the essay. States the question the whole essay will answer,
without yet arguing for an answer or introducing evidence. Names the subject
paper only as the essay's anchor/lens. Sets up paragraph 9, which returns to
and resolves this same framing.

**Prompt:** Write the essay's opening paragraph (~150 words). Do not open
with a paper introduction or a "this essay will discuss" statement. Instead,
open on the general tension that runs through the whole seminar session:
William Benzon treats ChatGPT as a black box and infers structure —
ontological categories, narrative templates — purely from repeated,
informal behavioral trials (a prompt, a response, a read on the pattern),
with no access to the model's internals. The question worth asking is
whether the structure he keeps finding this way (a "landscape" the model's
outputs roll downhill into, a recurring narrative "prototype," a stable
concrete/abstract asymmetry) is a genuine feature of the model, or an
artifact of how loosely each individual experiment samples its targets —
small, hand-picked trials standing in for a general claim. Name Benzon's own
working paper, "ChatGPT's Ontological Landscape," as the case this essay
will use to test that question, and signal (without yet arguing it) that the
sharpest evidence on either side turns out to come from tightening one of
his own experiments rather than from anything external. End on that note of
suspense rather than resolving it — the resolution belongs in the closing
paragraph, not here.

---

## 2. The subject paper's wager

**Role:** First paragraph of the essay's anchor section (the subject paper +
our sidenote, the largest and most central material). States the subject
paper's core argument/contribution (task criterion 1) evaluatively. Sets up
paragraphs 3 and 4, which bring in our own sidenote's two experimental
threads as the critical, non-summary engagement with this material.

**Prompt:** Write a paragraph (~160 words) making an evaluative argument
about what William Benzon's "ChatGPT's Ontological Landscape" (Nov 2023) is
actually claiming and staking, not a report of its contents. Benzon's method:
prompt ChatGPT with minimal, unconstrained instructions and read the
resulting pattern as diagnostic of the model's internal "landscape." Two
experiments anchor this. (1) Asked repeatedly for "a list of 20 things,
anything," the lists differ item-by-item but are drawn from "roughly the
same conceptual territory" — physical objects skewed toward a narrow,
recurring set (bicycle, hot air balloon, chocolate chip cookies, rainbow).
Benzon explains this via Waddington's epigenetic landscape metaphor: the
prompt drops a "ball" into activation space and it rolls downhill into a
valley shaped by "the lay of the land." (2) In "ChatGPT Plays 20 Questions,"
six targets (bicycle, squid, apple — concrete; justice, evolution, truth —
abstract), each played twice: "bicycle/squid/apple ran 19–31 questions with
several hints, while justice/evolution resolved in 7–9 questions with none,
and truth ... sat in between at 19–21 questions but needed the most hints of
any round." Argue that the real wager here is methodological as much as
substantive: that repeated, informal behavioral trials — without ever
touching weights or activations — can license a real claim about category
structure. Note that Benzon himself immediately hedges this wager: he calls
it "premature to ascribe any statistical significance to these findings" and
asks "What universe are we sampling and how do we choose our samples?" —
a self-doubt this essay will come back to. Do not resolve that hedge here;
just state it as the paper's own built-in fault line.

---

## 3. Our sidenote, thread one: escaping a seeded pocket

**Role:** Second paragraph of the anchor section. Brings in the first of our
own sidenote's two experimental threads as critical extension of the subject
paper's list-generation experiment — this is the "own sidenote" material the
task requires to do real evaluative work, not summary. Precedes paragraph 4,
which brings in the sidenote's second, stronger thread.

**Prompt:** Write a paragraph (~160 words) presenting our own sidenote's
first experiment as a deliberate variant probe of Benzon's landscape
metaphor, not a restatement of it. The sidenote prompts an LLM with "give me
20 things, anything, start with butterfly, dragonfly, ..." — the model
continues the "-fly" phonetic pattern, then, once exhausted, drifts outward
through flying bugs, general bugs, and flying mammals; asked for "50 more,"
it collapses further into general mammals. Argue that where Benzon's own
experiment drops the ball into a shallow, broad valley ("things") and
watches where it lands, this experiment does the inverse: it drops the ball
into a narrow, artificially seeded pocket and traces its escape back toward
the broad valley — testing a mechanism (does sustained pressure to keep
generating drive the model toward ever more generic categories) that
Benzon's landscape metaphor implies but never actually runs, since his own
trials are always fresh 20-item prompts, never an in-context extension of
an existing list. Then turn critical: note what the sidenote leaves
underdeveloped against Benzon's own methodological standard — it reports no
model version or session date, where Benzon is careful to log "the
September 25 version of ChatGPT" and the exact date/time of each trial; it
runs only once, where Benzon reruns his own list prompt three times
(including once after logging out) specifically to check whether a list is
"rigid"; and it never addresses temperature, which Benzon flags explicitly
("A temperature of zero (0) seems to eliminate ALL choice... I would
imagine that [the range of choices] varies with the value of the
temperature parameter") as a variable that would need to be fixed or known
before this kind of drift claim can be trusted.

---

## 4. Our sidenote, thread two: catching the paper's own confound

**Role:** Third and final paragraph of the anchor section, and the essay's
single strongest evaluative move. Brings in the sidenote's second thread,
which directly complicates the subject paper's headline 20-Questions
finding from paragraph 2. Sets up paragraphs 7–8, which will show this same
move echoed independently elsewhere in the session and sharpened into the
essay's central claim.

**Prompt:** Write a paragraph (~170 words) presenting our own sidenote's
second experiment as the piece of evidence that most directly interrogates
the subject paper's headline finding, and treat it as the paragraph's main
argument — not a neutral description. The sidenote runs a full
hypothesize → predict → test → catch-a-confound → fix → result arc on
Benzon's 20-Questions abstract/concrete asymmetry (see paragraph 2 for the
numbers): it hypothesizes that ChatGPT's first question is always
abstract-vs-concrete, and that because abstract words are rarer in the
English dictionary, disambiguating an abstract target takes fewer steps;
generalizes this to "a binary question always favors guessing the
less-frequent branch first"; then catches its own confound — the
concrete/abstract split used in Benzon's six targets doesn't match the true
concrete/abstract ratio in the English dictionary, so the observed asymmetry
could be an artifact of item selection rather than a property of the
model's questioning strategy; fixes it by sampling from a custom dictionary
with an equal concrete/abstract split and telling ChatGPT explicitly that
the target is drawn from that list; and finds no significant bias toward
either category. Also flag, as a second, independent overclaim the sidenote
catches: its own premise that the first question is "always" abstract/
concrete doesn't hold against Benzon's actual transcripts either — the
opening questions there are almost always about animacy or tangibility
first ("Is it a living thing?" / "Is it something you can touch?"), with the
abstract/concrete split typically surfacing only as the second or third
question (e.g., for justice: "Is it a living thing? No / Is it an object?
No / Is it a concept or idea? Yes" — question 3, not question 1). Frame the
paragraph's closing move as: this is the sidenote correcting Benzon's own
sampling on his own terms, using the exact kind of scrutiny his hedge in
paragraph 2 called for but didn't do himself.

---

## 5. The room, part one: the same attractor, stress-tested

**Role:** First paragraph of the comparison section (task criterion 2 —
relation to the other papers in the session). Reference material enters
here only to extend/stress-test the landscape/attractor phenomenon already
established as the subject paper's and our sidenote's shared subject in
paragraphs 2–4 — not as a parallel summary of the other papers. Precedes
paragraph 6, which brings in the second and more theoretically loaded
reference connection.

**Prompt:** Write a paragraph (~190 words) using material from two other
students' presentations in the session strictly as stress tests of the
landscape/attractor claim already on the table — every sentence should read
as "this tells us something about Benzon's/our claim," never as "this other
paper found X." From reference analysis1 (a student's presentation on
Benzon's later paper "ChatGPT tells 20 versions of its prototypical story"):
the student replicated Benzon's single-session-vs-separate-session design on
open-weight models and found that single-session runs were 10/10 coherent
while separate-session runs on Llama-3.1-8B were only 7/10 coherent, three
degenerating into token salad — their headline reframe is "session context
affects stability, not results." Argue this is the hard-collapse endpoint of
the same spectrum our sidenote's "50 more" experiment (paragraph 3) traces
softly, as semantic genericization rather than incoherence — the two
together suggest degeneration under sustained generation is a spectrum, not
a binary. Also from that presentation: comparing "story" (7/10 coherent) vs.
"tell me a story" / "write a story" (10/10 each) suggests prompt specificity,
not session history per se, buys coherence — offer this as a candidate,
previously unexamined variable behind our own sidenote's "50 more" drift
(the follow-up under-specifies the constraint the original prompt set).
Finally, note that the same presentation's DeepSeek-vs-Llama comparison
(DeepSeek "does not fail to produce coherent stories, it just has a
different default story") is an empirical test of a claim Benzon's subject
paper only speculates about — that the physical-object bias in his "20
things" lists is "an abstraction over the concepts in the universe of texts
on which ChatGPT was trained." From reference analysis2 (a second student's
presentation, on yet another Benzon story-substitution paper), add briefly:
that presentation separately cites a third Benzon paper reporting that bare
"story" prompts converge 19-out-of-20 times on the same narrative archetype
— the same default-attractor phenomenon, for stories instead of lists,
reinforcing rather than complicating the picture.

---

## 6. The room, part two: the forty-year-old machinery underneath

**Role:** Second paragraph of the comparison section. Brings in the
strongest and most direct reference connection — the discovery that a third
reference paper is Benzon's own decades-old theoretical apparatus. Closes
out criterion 2. Precedes paragraph 7, which pivots from specific
comparisons to the session-wide pattern.

**Prompt:** Write a paragraph (~185 words) arguing that reference paper 3 —
confirmed (via reference analysis3) to be Benzon's own 1985 report
"Ontology in Knowledge Representation," self-cited in the subject paper's
own Appendix — is not an external comparison at all but the theoretical
skeleton underneath the subject paper's 2023 experiments. Make the specific
case: paper3's "assignment tree" (object → plant → animal → human → social
person, with properties inherited upward) is, node for node, the Great
Chain of Being that the subject paper spends its "From Salt and NaCl to the
Great Chain" section probing in ChatGPT dialogue — and Benzon cross-
references this explicitly in the subject paper via a footnote to his own
2018 paper on the assignment relation. Then give the single sharpest
empirical instance: in the subject paper's 20-Questions "Apple" round,
ChatGPT's route runs through the substantive/paradigmatic hierarchy ("Is it
a plant?" → "Is it a type of tree?" → "Is it a deciduous tree?" →
"Is it a fruit-bearing tree?"), while an earlier round instead detours
through the functional/food hierarchy ("Is it related to food?" → kitchen →
"fruit used in cooking" → red-colored fruit guesses, repeating "currant"
twice) — enacting, unwittingly, exactly the substantive-versus-functional
paradigm split paper3 formalizes explicitly. Frame the paragraph's point as:
this isn't Benzon discovering new structure in ChatGPT so much as his own
38-year-old formal categories surfacing, unprompted, in a system that was
never given them directly — which raises the stakes on whether that
structure is really in the model, or is being read into it by an author who
already has the categories in hand before he starts prompting.

---

## 7. The session's real question: rigor as a shared reflex

**Role:** First paragraph of the synthesis section (task criterion 3 —
broader themes/tensions across the whole session). Pivots from individual
comparisons (paragraphs 5–6) to a pattern that spans the entire session.
Sets up paragraph 8, which sharpens this pattern into the essay's central,
most specific claim.

**Prompt:** Write a paragraph (~150 words) arguing that the session's real
shared question — not stated by any single presenter, visible only by
reading the presentations against each other — is whether Benzon's
small-sample, hand-picked working-paper method can bear the weight of the
general claims it makes, and that multiple, independent presentations
converged on the same diagnosis and the same fix. From reference analysis1:
the student's rubric-scored replication (an 8-point coherence rubric across
30 trials, three models) turns Benzon's impressionistic reading into a
countable outcome. From reference analysis2: that presentation's proposed
protocol (generate n stories per condition, control model version/
temperature/session history, test statistically) explicitly reframes
Benzon's method as needing to move "from observation to characterisation";
note too that Benzon himself half-anticipates this in that same paper,
rerunning one transformation "at the beginning of a session several days
after" the original specifically to check reproducibility. And from our own
sidenote (paragraph 4): the concrete/abstract dictionary-balancing fix is
the same diagnose-an-uncontrolled-variable-then-formalize-it move, run on
the subject paper itself. Argue that three independent presentations
reaching for the same remedy — larger N, controlled sampling — is stronger
evidence of a real, session-wide methodological gap than any one of them
alone.

---

## 8. Sharpening the answer: theory and rerun converge

**Role:** Second and final paragraph of the synthesis section, and the
essay's most pointed claim. Sharpens paragraph 7's general pattern into a
specific verdict on the subject paper's own headline finding, by bringing
theory (reference analysis3's Naco) and evidence (our own sidenote) together.
Precedes paragraph 9, the closing paragraph, which steps back from this
specific claim to the essay's opening frame.

**Prompt:** Write a paragraph (~150 words) making the essay's sharpest
claim: that the subject paper's own headline finding is the clearest
casualty of the rigor problem named in paragraph 7. From reference
analysis3: Enea Naco's presentation on Benzon's 1985 paper argues that LLMs
are fluent on the surface but exhibit "no explicit ontological structure,
only statistical patterns," performing unreliably in "high sensitivity
domains" — a verdict Naco reaches from theory, without ever seeing our
sidenote's result. Argue that our sidenote's own controlled rerun
(paragraph 4) — finding no significant concrete/abstract bias once sampling
is balanced — is the empirical confirmation of exactly that verdict, aimed
at the specific claim (the subject paper's abstract/concrete asymmetry)
that looked most like real ontological competence. Note the irony
explicitly: Benzon's own hedge in paragraph 2 ("What universe are we
sampling and how do we choose our samples?") turns out to have been the
right question, and it's answered — in the negative, against his own
finding — not by an outside critic but by a controlled rerun of his own
experiment. Close by stating plainly that this is the strongest connection
the whole session makes to the subject paper: a theory-driven skepticism
and a controlled-sampling rerun, arrived at independently, landing on the
same conclusion.

---

## 9. Where this leaves us

**Role:** Closing paragraph. Returns to and resolves the question posed in
paragraph 1 (landscape or artifact?). Introduces no new material — every
claim it makes should already have appeared in paragraphs 2–8. Light touch,
matching the task's "no strict form"/blog-post-style guidance for a close
that doesn't restate a formal thesis mechanically.

**Prompt:** Write the essay's closing paragraph (~195 words). Return to the
question posed in the opening paragraph — whether the structure Benzon
keeps finding (the landscape metaphor, the narrative prototype, the
assignment tree, the concrete/abstract asymmetry) is real or an artifact of
loose sampling — and answer it without introducing new evidence. Argue that
the honest answer is mixed and asymmetric across the subject paper's two
experiments: the "20 things" landscape/prototype phenomenon survives
stress-testing reasonably well (echoed independently in reference analysis1
and analysis2's story experiments, and even empirically deepened by
reference analysis3's 1985 assignment-tree machinery), while the
20-Questions concrete/abstract asymmetry — the paper's most quotable,
headline-sounding finding — does not survive its own author's method being
taken seriously, once our own sidenote actually runs the controlled version
Benzon's own hedge called for. Close on the observation that this asymmetry
is itself the paper's most interesting result, even though (or because) it
cuts against the paper's own apparent conclusion: an informal, small-n,
behavioral method can generate real and durable metaphors while also
generating findings that don't survive contact with rigor — and the session
as a whole, read together rather than paper by paper, is really a case
study in telling those two outcomes apart. Do not introduce any reference
paper's content that hasn't already appeared earlier in the essay.
