import fatass

from .patterns import Patterns


def search():
    print("search: starting web search for sentences that give away AI-generated text")
    node = Patterns()
    csv_text = fatass.free(
        readable=[],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        prompt=r"""Search the web for sentences and phrases that are commonly cited as
telltale signs of AI-generated text (e.g. phrases like "As an AI language
model", "In conclusion", "It's important to note that", "I hope this
helps", "Let's dive in", "a testament to", "in today's fast-paced world",
etc.), drawn from articles, guides, and discussions about detecting or
avoiding AI-sounding writing.

Also search for telltale *inter-sentence* patterns -- not single give-away
phrases, but characteristic relationships between consecutive sentences
or clauses that flag AI-generated text (e.g. a rule-of-three list
followed by a summarizing clause, a claim immediately followed by a
"this is because/this means" restatement, a short punchy sentence
following a long one for rhetorical effect, a setup sentence paired with
a contrasting "however/but" follow-up, etc.).

Also search for telltale *narrative/structural* patterns -- paragraph- or
document-level habits, not single sentences (e.g. opening with a
throat-clearing definition/history before getting to the point, an
introduction that restates the question before answering it, a closing
paragraph that recaps "In summary/Overall" instead of adding new content,
heavy use of parallel triplets ("not only... but also... and"), a
conclusion that circles back to the introduction's exact wording, or
a numbered/bulleted structure imposed on content that doesn't need it).

Also search for telltale *word-level* patterns -- individual words or
word choices that are disproportionately common in AI-generated text
(e.g. "delve", "boast", "leverage", "showcase", "underscore", "tapestry",
"vibrant", "robust", "intricate", "seamless", "landscape" used
metaphorically, "realm", "elevate", "foster", "unlock", "navigate" used
metaphorically), including distinctive word-formation habits (e.g.
overuse of "-ing" participle openers, gerund stacking, or em-dash-heavy
sentences).

Also search for telltale *intra-sentence* patterns -- structural habits
within a single sentence, distinct from individual word choice (e.g. the
"not just X, but Y" / "not only X, but also Y" construction, "it's not
about X, it's about Y", a triadic list packed into one sentence ("X, Y,
and Z" used as a rhetorical flourish rather than a plain enumeration),
a sentence opening with a dependent clause before the subject
("By doing X, you can Y"), or a colon-introduced appositive used for
emphasis ("The result: something").

Collect a good list of the single-phrase telltales, the inter-sentence
telltales, the narrative/structural telltales, the word-level telltales,
and the intra-sentence telltales, group them into families of variants
(e.g. different tenses, synonyms, punctuation, or -- for inter-sentence,
narrative, and intra-sentence patterns -- different connecting
words/structures or clause shapes), and for each family write one
regex pattern that matches that family and its variants. For an
inter-sentence family, the regex should span the relationship itself
(e.g. matching across the sentence boundary, such as
`[^.!?]+[.!?]\s+(However|But|Yet),\s`), not just one side of it. For a
narrative/structural family where a single regex genuinely can't capture
a document-level shape, write the closest reasonable regex approximation
(e.g. matching the characteristic opening/closing phrase of that
structural habit) and note the limitation in the description field.

Report your result as a CSV with header `pattern,description,examples`,
where:
- `pattern` is the regex (Python `re` syntax) for that family,
- `description` is a short label for what the family represents,
- `examples` is a `;`-separated list of 2-4 real example sentences/phrases
  that the pattern should match.

Return the full CSV text (including header row) as your result.""",
    )
    print("search: writing result to _.csv")
    (node._assets_dir() / "_.csv").write_text(csv_text, encoding="utf-8")
