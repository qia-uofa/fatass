# AI Writing Patterns: A Guide to Avoiding Them

This guide documents the recognizable tells of AI-generated prose, split
into **micro** patterns (word- and sentence-level) and **macro** patterns
(paragraph- and essay-level structure), with concrete fixes for each. Use
it while drafting or revising this essay to keep the prose reading as a
specific person's argument rather than generic model output.

## Why this matters

Research on LLM output shows it carries a consistent, detectable
"fingerprint" — linguistic markers that persist across topics and even
across explicit style instructions (Detecting Stylistic Fingerprints of
Large Language Models, arXiv). Stylometric analysis finds AI text is, on
average, more formal, more structurally uniform, more hedged, and lower
in lexical variety than human writing (A linguistic comparison between
human- and AI-generated content, PMC/ScienceDirect). None of that is
disqualifying on its own — but it means the *safest* default output of
any single generation pass is also the most recognizable one. Deliberate
variation is what breaks the fingerprint.

## Micro patterns (word / sentence level)

**Stock vocabulary.** Certain words are wildly over-represented in AI
output relative to normal usage: *delve, moreover, crucial, landscape,
tapestry, leverage, unlock, harness, robust, seamless, nestled, plethora,
multitude, pivotal, transformative, game-changer, revolutionize*. If one
of these is the first word that comes to mind, treat it as a prompt to
find a plainer, more specific alternative — or to cut the sentence
entirely (Pangram; ContentBeta 2026 word list; HumanizeThisAI).

**Uniform sentence length.** Human writing naturally mixes short, blunt
sentences with longer, subordinate-clause-heavy ones. AI output tends
toward a narrow band of medium-length sentences, producing a flat,
metronomic rhythm (Pangram, "Comprehensive Guide to Spotting AI Writing
Patterns"). Fix: read a paragraph aloud; if every sentence takes about
the same breath, break one up or fuse two.

**The negation-contrast frame — "It's not just X, it's Y."** This
construction (and its cousins: "it's not just about X — it's about Y")
is one of the single most identified AI tells; a Washington Post analysis
of hundreds of thousands of ChatGPT messages found it among the most
overused constructions in the corpus (Blake Stockton, "Don't Write Like
AI"; Washington Post analysis cited via Pangram). It reads as
sophistication but is almost always padding — the sentence usually says
as much or more with the negation removed. Fix: state the claim directly;
if a real contrast is being drawn, name what's actually being contrasted
instead of the empty X/Y slot.

**The hedge.** Phrases like "on the one hand... on the other hand," "while
some may argue," or "it's worth noting that" let the model avoid
committing to a position — output tuned to sound neutral rather than
argued (Pangram; PMC/ScienceDirect comparison notes AI text's "subtler use
of cognitive expressions" and more hedging than human text). This essay's
own brief explicitly warns against this: criterion 1 asks for evaluation
of the subject paper's argument, not a balanced non-committal summary of
it. Fix: take a side. If genuine uncertainty exists, say specifically what
is uncertain and why, rather than gesturing at "both sides."

**Reflexive em dash use.** Recent models show a statistical preference
for em dashes to link clauses, used so often that the punctuation itself
has become a tell (Pangram). An occasional dash is fine; a dash in nearly
every paragraph is not. Fix: alternate with periods, semicolons, or plain
conjunctions; ask whether the dash is doing real work or just gluing two
half-formed thoughts together.

**Throat-clearing phrases.** "It is important to note that," "It's worth
mentioning," "needless to say" — these add length without adding content
and are common AI filler (search results across Pangram, ContentBeta,
umanwrite 2026 lists). Fix: delete the frame and keep the claim.

**Cliché idioms used as connective tissue.** "The smoking gun," "a
perfect storm," "move the needle," "tip of the iceberg," "double-edged
sword," "at the end of the day" — these function as pre-packaged
transitions that let the writer skip actually reasoning through the
connection between two ideas (Stackedo, "Top Worst AI Writing Clichés").
Fix: replace the idiom with the actual logical connector ("this matters
because...", "which implies...", "in contrast to...").

## Macro patterns (paragraph / essay level)

**The rigid five-part shape.** AI defaults to a highly regular macro
structure: an introduction that previews the thesis, three or four body
paragraphs each opening with a clean topic sentence, and a conclusion
that restates what was just said. The structure is so repeatable that
swapping in a new topic doesn't change its shape at all (Bloomberry,
"AI Sentence Structure"; Getting Smart, "The Formulaic Trap"). This
essay's task explicitly says "no strict form... we expect your essay to
adhere to," and offers essayistic blog posts as its model — a signal to
break from this shape, not reproduce it. Fix: let the argument's own
logic set the paragraph count and order (this essay's `skeleton.md`
should already do this); don't pad or trim to fit four body paragraphs
for their own sake.

**The rule-of-three list, deployed reflexively.** Three-item lists are
genuinely persuasive — they read as complete and well-organized, which is
exactly why AI overuses them for *everything*, including places where the
real number of relevant points is two, four, or one (GPTZero, "How to
Break Free from GPT's Rule of Three"; Wikipedia, "Rule of three
(writing)"). A pattern that shows up in nearly every paragraph stops
reading as rhetorical craft and starts reading as a tic. Fix: let the
material dictate the count. If there are two strong pieces of evidence,
use two. Reserve the triad for places where three genuinely is the right
number.

**The summary-only conclusion.** "In conclusion," "In summary," "At the
end of the day," "Ultimately" followed by a restatement of points already
made is a direct callback to five-paragraph-essay training data, and it's
one of the most reliable tells because humans, left to their own devices,
usually end on a final thought, a complication, or an implication — not a
recap (Oliviacal, "How to Spot AI Writing Tells"). This essay's own
outline plan (`analysis/task/plan.md`) already commits to this: the
closing section should complicate or answer the opening's framing, not
restate sections 2–4. Fix: cut any conclusion paragraph that could be
deleted without losing information — if it's pure restatement, it isn't
adding anything.

**False-balance synthesis.** At the point where an essay is supposed to
synthesize across sources (this essay's Section 4, on the unresolved
question across the symposium), AI defaults to a neutral "there are
valid points on all sides" summary rather than staking out where the
tension actually leaves the argument (PMC/ScienceDirect: AI text trends
"emotionally positive" and "motivational" rather than committing to a
specific, possibly unresolved, stance). Fix: name what remains genuinely
open and say what would resolve it, rather than presenting the
disagreement itself as the destination.

**Uniform paragraph rhythm across the whole piece.** Beyond sentence
length, AI output tends toward paragraphs of similar length and internal
shape (claim, then two or three supporting sentences, repeat) — this is
the paragraph-level version of the sentence-length tell above (Bloomberry;
PMC/ScienceDirect on lower variance generally). Fix: let a paragraph that
needs to be short (a pivot, a single sharp claim) stay short, and let one
that's doing real analytical work run long, rather than smoothing every
paragraph to the same size.

## Quick self-check before finalizing

- Read each paragraph's opening sentence in sequence. If they all sound
  interchangeable ("This section examines...", "Another key aspect..."),
  the macro structure is on autopilot.
- Search the draft for: *delve, moreover, crucial, landscape, tapestry,
  leverage, robust, seamless, pivotal, "it's not just," "it's important
  to note," "in conclusion," "at the end of the day."* Cut or replace
  every hit.
- Count em dashes per paragraph. More than one is worth a second look.
- Check whether the conclusion says anything the body didn't already say.
  If not, cut it down to the one thing it actually adds.
- Check every three-item list: would two or four items be more honest to
  the material?

## Sources

- [Comprehensive Guide to Spotting AI Writing Patterns — Pangram](https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns)
- [Walking Through AI's Most Overused Phrases — Pangram](https://www.pangram.com/blog/walking-through-ai-phrases)
- [List of 300+ AI Words, Phrases and Sentences to Avoid (2026) — ContentBeta](https://www.contentbeta.com/blog/list-of-words-overused-by-ai/)
- [50 Words AI Overuses (And What to Write Instead) — HumanizeThisAI](https://humanizethisai.com/blog/50-words-ai-overuses)
- [Common AI Words and Phrases to Avoid in 2026 — umanwrite](https://www.umanwrite.com/articles/common-ai-words-phrases-list)
- [How to Spot AI Writing Tells: 17 Examples + AI Words Blacklist 2026 — Oliviacal](https://www.oliviacal.com/post/ai-writing-tells)
- [Don't Write Like AI (1 of 101): "It's Not X, it's Y" — Blake Stockton](https://www.blakestockton.com/dont-write-like-ai-1-101-negation/)
- [Top Worst AI Writing Clichés (And How to Fix Them) — Stackedo](https://stackedo.com/ai-writing-cliches-to-avoid/)
- [AI Writing Tropes to Avoid — tropes.fyi](https://gist.github.com/ossa-ma/f3baa9d25154c33095e22272c631f5a1)
- [Detecting Stylistic Fingerprints of Large Language Models — arXiv](https://arxiv.org/html/2503.01659v1)
- [A linguistic comparison between human- and AI-generated content — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12969083/)
- [AI Sentence Structure: The Formulaic Patterns That Make AI Writing Recognizable — Bloomberry](https://www.bloomberry.ai/research/ai-sentence-structure)
- [The Formulaic Trap: Why AI Finds Your Assignments Easy — Getting Smart](https://www.gettingsmart.com/2026/05/21/the-formulaic-trap-why-ai-finds-your-assignments-easy/)
- [How to Break Free from GPT's Rule of Three in Writing — GPTZero](https://gptzero.me/news/the-rule-of-three/)
- [Rule of three (writing) — Wikipedia](https://en.wikipedia.org/wiki/Rule_of_three_(writing))
