import fatass
from fatass.topology.archive.seminar_essay.drafting.draft import (
    Draft as Draft,
)
from fatass.topology.archive.seminar_essay.style.ai_pattern import (
    AiPattern as AiPattern,
)


def build(draft: Draft, ai_pattern: AiPattern):
    fatass.free(
        silent=True,
        model="opus",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[draft, ai_pattern],
        prompt=(
            f"Read every file in the readable directory for this node's "
            f"`draft` dependency: the current draft of the essay. Also "
            f"read every file in the readable directory for this node's "
            f"`ai_pattern` dependency: a reference describing patterns "
            f"typical of AI-generated writing, both micro (word- and "
            f"sentence-level: stock phrasing, hedges, filler transitions, "
            f"listy parallelism, overuse of certain constructions, etc.) "
            f"and macro (paragraph- and essay-level: formulaic structure, "
            f"symmetrical section lengths, mechanical topic-sentence/"
            f"evidence/wrap-up rhythm, over-signposting, etc.).\n\n"
            f"Go through the draft in order, at whatever granularity each "
            f"pattern actually operates at: a single line, a single "
            f"sentence, a pair of adjacent sentences, or a larger group of "
            f"consecutive sentences/paragraphs for patterns that only show "
            f"up across a span. Record every unit that shows a micro-level "
            f"AI pattern, a macro-level AI pattern, or both; a unit can "
            f"carry more than one pattern. Units with no AI pattern need "
            f"no entry.\n\n"
            f"Write a single document, `annotation.md`, in the current "
            f"directory: one entry per flagged line, sentence, sentence "
            f"pair, or group, quoting the text verbatim, naming which "
            f"pattern(s) from `ai_pattern` it matches (micro, macro, or "
            f"both), and briefly explaining why it reads as AI-patterned "
            f"rather than just plain or formulaic prose."
        ),
    )
