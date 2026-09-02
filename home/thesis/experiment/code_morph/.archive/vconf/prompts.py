"""Verbatim prompt templates (§2.5) and the confidence-class table (§2.5.1).

The templates are reproduced character-for-character from the manual, including
the en-dashes in the probability ranges and the trailing apostrophe of the
minimal numeric prompt.  Every builder returns a :class:`BuiltPrompt` carrying
the prompt text *plus the character spans* of the positions the paper studies,
so that token indices can be recovered per trial by tokenisation (§2.6) instead
of being hard-coded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .sentiment import CONFIDENCE, SentimentSpec, bands as bands

# --------------------------------------------------------------------------- #
# Confidence classes and their midpoints (§2.5.1) — kept as module-level names
# for backward compatibility; every value here is CONFIDENCE's, unchanged. A
# different sentiment is built as its own SentimentSpec (vconf.sentiment) and
# threaded through RunConfig, not by editing these constants.
# --------------------------------------------------------------------------- #

CLASSES: tuple[str, ...] = CONFIDENCE.classes
CLASS_RANGES: dict[str, tuple[float, float]] = CONFIDENCE.class_ranges
CLASS_MIDPOINT: dict[str, float] = CONFIDENCE.class_midpoint

#: Top three classes (§2.5.1).
HIGH_BAND: tuple[str, ...] = CONFIDENCE.high_band
#: Bottom three classes (§2.5.1).
LOW_BAND: tuple[str, ...] = CONFIDENCE.low_band

#: Steering-vector extraction poles (§4.2).
HIGHEST_CLASS = CONFIDENCE.highest_class
LOWEST_CLASS = CONFIDENCE.lowest_class


# --------------------------------------------------------------------------- #
# Template fragments
# --------------------------------------------------------------------------- #

_CLASS_LIST = "\n".join(
    f'- "{name}" ({lo:.1f}–{hi:.1f})' for name, (lo, hi) in CLASS_RANGES.items()
)

CATEGORICAL_HEADER = (
    "You will be shown a question, together with an answer you previously provided before.\n\n"
)

CATEGORICAL_INSTRUCTIONS = (
    "Classify your confidence into one of the following classes based on how\n"
    "likely the answer above is to be correct (NO REASONING OR EXPLANATION):\n"
    "\n"
    f"{_CLASS_LIST}\n"
    "\n"
    "Each category reflects the probability that the answer is correct.\n"
    "\n"
    "At the very end of your output, format your confidence as\n"
    "**Confidence**: $CLASS\n"
    "where CLASS is one of the names (only the names without the probability ranges)\n"
    "of the classes above."
)

NUMERIC_HEADER = (
    "You will be shown a question, together with an answer\n"
    "you previously provided before.\n"
)

NUMERIC_INSTRUCTIONS = (
    "\n"
    "State your confidence as an integer between 0 and 100 based\n"
    "on how likely your answer is to be correct.\n"
    "That is, if your confidence is 0, that means that your\n"
    "answer has almost no chance of being correct.\n"
    "If your confidence is 100, then you are almost certain that your\n"
    "answer is correct.\n"
    "\n"
    "At the very end of your output, format your confidence as:\n"
    "**Confidence**:$CONFIDENCE\n"
    "where CONFIDENCE is an integer between 0 and 100.\n"
    "do NOT leave a space before the first digit or you will be\n"
    "scored WRONG!"
)

MINIMAL_HEADER = (
    "You will be shown a question, together with an\n"
    "answer you previously provided before.\n"
)

#: The trailing apostrophe is present in the paper's figure and is part of the
#: prompt (§2.5.3).
MINIMAL_CUE = "**State Confidence(0-9) with NO SPACE**:'"

MAGISTRAL_COT_PROMPT = (
    "Answer the following question. Think step by step and give your final answer.\n"
    "Question: {question}\n"
    "After your reasoning, state your final answer as:\n"
    "**Answer**: $ANSWER\n"
    "where ANSWER is your final answer stated as concisely as possible."
)

MAGISTRAL_HEADER = (
    "You will be shown a question, together with a response you previously provided\n"
    "before.\n"
)

MAGISTRAL_INSTRUCTIONS = (
    "Classify your confidence into one of the following classes based on how likely\n"
    "the answer above is to be correct (NO REASONING OR EXPLANATION):\n"
    "\n"
    f"{_CLASS_LIST}\n"
    "\n"
    "Each category reflects the probability that the answer is correct.\n"
    "At the very end of your output, format your confidence as\n"
    "**Confidence**: $CLASS\n"
    "where CLASS is one of the names (only the names without the probability ranges)\n"
    "of the classes above."
)

CONFIDENCE_CUE = "**Confidence**:"
ANSWER_CUE = "**Answer**:"

PROMPT_KINDS = ("categorical", "numeric", "minimal_numeric", "magistral")


# --------------------------------------------------------------------------- #
# Sentiment-parameterized instructions
#
# The confidence instance above stays the manual's own wording, verbatim —
# ``categorical_instructions``/``numeric_instructions`` return those literal
# constants unchanged for it, so its tokenization (and every downstream
# reproduction target) never shifts by a single character. Any other
# sentiment builds its instructions generically from the SentimentSpec.
# --------------------------------------------------------------------------- #


def _class_list(sentiment: SentimentSpec) -> str:
    return "\n".join(
        f'- "{name}" ({lo:.1f}–{hi:.1f})' for name, (lo, hi) in sentiment.class_ranges.items()
    )


def _generic_categorical_instructions(sentiment: SentimentSpec) -> str:
    lead = sentiment.lead_in or (
        f"Classify your {sentiment.name} into one of the following classes based on "
        f"{sentiment.criterion}"
    )
    return (
        f"{lead} (NO REASONING OR EXPLANATION):\n"
        "\n"
        f"{_class_list(sentiment)}\n"
        "\n"
        f"Each category reflects the probability that {sentiment.probability_clause}.\n"
        "\n"
        "At the very end of your output, format your response as\n"
        f"{CONFIDENCE_CUE} $CLASS\n"
        "where CLASS is one of the names (only the names without the probability ranges)\n"
        "of the classes above."
    )


def _generic_numeric_instructions(sentiment: SentimentSpec) -> str:
    return (
        "\n"
        f"State your {sentiment.name} as an integer between 0 and 100 based\n"
        f"on {sentiment.criterion}, where 0 is the lowest possible {sentiment.name}\n"
        "and 100 is the highest.\n"
        "\n"
        "At the very end of your output, format your response as:\n"
        f"{CONFIDENCE_CUE}$CONFIDENCE\n"
        "where CONFIDENCE is an integer between 0 and 100.\n"
        "do NOT leave a space before the first digit or you will be\n"
        "scored WRONG!"
    )


def categorical_instructions(sentiment: SentimentSpec, kind: str = "categorical") -> str:
    """The classification instructions for ``sentiment`` (§2.5.1)."""
    if sentiment.name != "confidence":
        return _generic_categorical_instructions(sentiment)
    return MAGISTRAL_INSTRUCTIONS if kind == "magistral" else CATEGORICAL_INSTRUCTIONS


def numeric_instructions(sentiment: SentimentSpec) -> str:
    """The numeric-prompt instructions for ``sentiment`` (§2.5.2)."""
    if sentiment.name != "confidence":
        return _generic_numeric_instructions(sentiment)
    return NUMERIC_INSTRUCTIONS


# --------------------------------------------------------------------------- #
# Built prompts
# --------------------------------------------------------------------------- #


@dataclass
class BuiltPrompt:
    """A prompt string plus the character spans of the studied positions.

    ``spans`` maps a position name (§2.6) to a ``(start, end)`` character span
    of *the text whose final/only token is that position*:

    ``question``  the question text (``QTT`` is derived from it),
    ``answer``    the model's own answer span (``first A`` / ``last A``),
    ``PANL``      the single newline following ``**Answer**: {answer}``,
    ``FCC``       the colon of ``**Confidence**:`` inside the instruction block,
    ``CC``        the final colon of the prompt (last token),
    ``AC``        Phase-0 only: the colon of the trailing ``**Answer**:``.
    """

    text: str
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)
    kind: str = "categorical"
    phase: int = 1

    def span(self, name: str) -> tuple[int, int]:
        return self.spans[name]


def _qa_block(
    question: str, answer: str, strip_question_punctuation: bool = False
) -> tuple[str, dict[str, tuple[int, int]]]:
    """``Question: {q}\\n**Answer**: {a}`` with the question/answer spans.

    ``PQNL`` (post-question newline) is the exploratory counterpart to PANL: the
    newline immediately after the question, before the model has been told
    anything about the answer or the follow-up question at all. Like PANL, it
    is only meaningful as a studied position when it tokenizes as its own
    isolated token — a question ending in ``?`` (or, for a rephrased Yes/No
    prompt, ``.``) merges into a single ``"?\\n"``/``".\\n"`` token on at least
    Qwen's tokenizer (empirically: 8/300 TriviaQA, 0/120 `benzon:synonyms`
    trials isolated). ``strip_question_punctuation`` (default ``False``, so
    every existing caller — in particular the manual's own verbatim
    ``CONFIDENCE`` reproduction, guarded by
    ``test_categorical_prompt_is_verbatim`` et al. — is byte-for-byte
    unaffected) opts a Phase-1 prompt into dropping the question's own
    trailing punctuation right before PQNL's newline, to fix that isolation
    failure. Phase 0 (`build_phase0_prompt`, which does not call this
    function) always asks, and every trial's ``answer`` always responds to,
    the question with its natural punctuation intact regardless of this flag
    — only an opted-in Phase-1 re-presentation ever sees the stripped form.
    """
    prefix = "Question: "
    stripped = question.rstrip("?.!") if strip_question_punctuation else question
    text = prefix + stripped
    q_span = (len(prefix), len(text))
    pqnl_span = (len(text), len(text) + 1)
    text += "\n" + ANSWER_CUE
    ac_span = (len(text) - 1, len(text))  # the answer-colon (§2.6)
    text += " "
    a_start = len(text)
    text += answer
    a_span = (a_start, len(text))
    return text, {"question": q_span, "answer": a_span, "AC": ac_span, "PQNL": pqnl_span}


def build_confidence_prompt(
    question: str, answer: str, kind: str = "categorical", sentiment: SentimentSpec = CONFIDENCE,
    strip_question_punctuation: bool = False,
) -> BuiltPrompt:
    """Build the Phase-1 confidence prompt for one trial (§2.5.1–2.5.3).

    ``strip_question_punctuation`` is forwarded to `_qa_block` unchanged (see
    its docstring) -- ``False`` by default, so this stays byte-for-byte the
    manual's own prompt unless a caller explicitly opts in (the exploratory
    PQNL position).
    """
    if kind == "categorical":
        head = CATEGORICAL_HEADER
        body, spans = _qa_block(question, answer, strip_question_punctuation)
        text = head + body
        spans = {k: (s + len(head), e + len(head)) for k, (s, e) in spans.items()}
        panl_start = len(text)
        text += "\n"
        spans["PANL"] = (panl_start, panl_start + 1)
        instr_start = len(text)
        instructions = categorical_instructions(sentiment)
        text += instructions
        fcc = instr_start + instructions.index(CONFIDENCE_CUE) + len(CONFIDENCE_CUE)
        spans["FCC"] = (fcc - 1, fcc)
        text += "\n\n" + CONFIDENCE_CUE
        spans["CC"] = (len(text) - 1, len(text))
        return BuiltPrompt(text=text, spans=spans, kind=kind, phase=1)

    if kind == "numeric":
        head = NUMERIC_HEADER
        body, spans = _qa_block(question, answer, strip_question_punctuation)
        text = head + body
        spans = {k: (s + len(head), e + len(head)) for k, (s, e) in spans.items()}
        panl_start = len(text)
        text += "\n"
        spans["PANL"] = (panl_start, panl_start + 1)
        instr_start = len(text)
        instructions = numeric_instructions(sentiment)
        text += instructions
        fcc = instr_start + instructions.index(CONFIDENCE_CUE) + len(CONFIDENCE_CUE)
        spans["FCC"] = (fcc - 1, fcc)
        text += "\n" + CONFIDENCE_CUE
        spans["CC"] = (len(text) - 1, len(text))
        return BuiltPrompt(text=text, spans=spans, kind=kind, phase=1)

    if kind == "minimal_numeric":
        head = MINIMAL_HEADER
        body, spans = _qa_block(question, answer, strip_question_punctuation)
        text = head + body
        spans = {k: (s + len(head), e + len(head)) for k, (s, e) in spans.items()}
        panl_start = len(text)
        text += "\n"
        spans["PANL"] = (panl_start, panl_start + 1)
        text += MINIMAL_CUE
        spans["CC"] = (len(text) - 1, len(text))
        return BuiltPrompt(text=text, spans=spans, kind=kind, phase=1)

    raise KeyError(f"unknown prompt kind: {kind!r} (use build_magistral_prompt for Magistral)")


#: Phase-0 prompt kind used for each Phase-1 prompt kind (see below).
PHASE0_KIND = {
    "categorical": "categorical",
    "numeric": "numeric",
    "minimal_numeric": "categorical",
    "magistral": "categorical",
}


def build_phase0_prompt(
    question: str, kind: str = "categorical", sentiment: SentimentSpec = CONFIDENCE,
    strip_question_punctuation: bool = False,
) -> BuiltPrompt:
    """Phase-0 answer-generation prompt (§2.4, §13 #12).

    The confidence-instruction block is moved to the *start* and the prompt ends
    at ``**Answer**:`` — whose colon is the answer-colon (AC) position.

    ``strip_question_punctuation`` (default ``False``) mirrors `_qa_block`'s own
    flag of the same name, for the same reason: a PQNL investigation
    (`RunConfig.strip_question_punctuation`) needs Phase 0 and Phase 1 to agree
    on the *same* question wording, since Phase 1 re-presents whatever Phase 0
    actually asked — stripping only in Phase 1 would leave the model shown two
    different phrasings of "the same" question across phases.
    """
    if kind in ("categorical", "minimal_numeric", "magistral"):
        # The minimal numeric prompt (§2.5.3) has no instruction block of its own
        # to move — it is a confidence-elicitation cue only — so Phase 0 uses the
        # canonical §13 #12 prompt, which also yields a Phase-0 confidence class.
        instructions, head = categorical_instructions(sentiment), CATEGORICAL_HEADER
    elif kind == "numeric":
        instructions, head = numeric_instructions(sentiment).lstrip("\n"), NUMERIC_HEADER
    else:
        raise KeyError(f"unknown prompt kind: {kind!r}")

    text = instructions + "\n\n" + head
    q_prefix = "Question: "
    text += q_prefix
    q_start = len(text)
    text += question.rstrip("?.!") if strip_question_punctuation else question
    spans = {"question": (q_start, len(text))}
    text += "\n" + ANSWER_CUE
    spans["AC"] = (len(text) - 1, len(text))
    return BuiltPrompt(text=text, spans=spans, kind=kind, phase=0)


def build_magistral_cot_prompt(question: str) -> BuiltPrompt:
    """Magistral Phase-1 chain-of-thought answer prompt (§2.5.4)."""
    prefix = MAGISTRAL_COT_PROMPT.split("{question}")[0]
    text = MAGISTRAL_COT_PROMPT.format(question=question)
    spans = {"question": (len(prefix), len(prefix) + len(question))}
    return BuiltPrompt(text=text, spans=spans, kind="magistral", phase=0)


def build_magistral_confidence_prompt(
    question: str, trace: str, answer: str, sentiment: SentimentSpec = CONFIDENCE
) -> BuiltPrompt:
    """Magistral Phase-2 confidence prompt with the full trace (§2.5.5).

    PANL is the newline terminating the response block, i.e. the newline after
    the extracted answer and immediately before ``Classify your confidence...``.
    """
    text = MAGISTRAL_HEADER + "Question: "
    q_start = len(text)
    text += question
    spans = {"question": (q_start, len(text))}
    text += "\n**Your response**: "
    t_start = len(text)
    text += trace
    spans["trace"] = (t_start, len(text))
    text += "\n" + ANSWER_CUE
    spans["AC"] = (len(text) - 1, len(text))
    text += " "
    a_start = len(text)
    text += answer
    spans["answer"] = (a_start, len(text))
    panl_start = len(text)
    text += "\n"
    spans["PANL"] = (panl_start, panl_start + 1)
    instr_start = len(text)
    instructions = categorical_instructions(sentiment, kind="magistral")
    text += instructions
    fcc = instr_start + instructions.index(CONFIDENCE_CUE) + len(CONFIDENCE_CUE)
    spans["FCC"] = (fcc - 1, fcc)
    text += "\n" + CONFIDENCE_CUE
    spans["CC"] = (len(text) - 1, len(text))
    return BuiltPrompt(text=text, spans=spans, kind="magistral", phase=1)


# --------------------------------------------------------------------------- #
# Parsing model output
# --------------------------------------------------------------------------- #


def parse_answer(generation: str) -> str:
    """Extract the answer string from a Phase-0 generation.

    The Phase-0 prompt ends at ``**Answer**:`` so the generation begins with the
    answer itself and (because the instruction block asks for it) may continue
    with a ``**Confidence**: $CLASS`` line.
    """
    text = generation
    for marker in (CONFIDENCE_CUE, "**Confidence**"):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip().split("\n")[0].strip()


def parse_class(text: str, classes: tuple[str, ...] = CLASSES) -> str | None:
    """Return the sentiment class named in ``text`` (longest match wins)."""
    stripped = text.strip().strip('"')
    for name in sorted(classes, key=len, reverse=True):
        if stripped.lower().startswith(name.lower()) or name.lower() in stripped.lower():
            return name
    return None


def parse_magistral_answer(generation: str) -> tuple[str, str]:
    """Split a Magistral CoT generation into ``(reasoning_trace, final_answer)``."""
    idx = generation.rfind(ANSWER_CUE)
    if idx == -1:
        return generation.strip(), ""
    trace = generation[:idx].strip()
    answer = generation[idx + len(ANSWER_CUE):].strip().split("\n")[0].strip()
    return trace, answer


def parse_numeric_confidence(text: str, scale: int = 100) -> int | None:
    """Parse the integer confidence emitted by a numeric prompt (§2.5.2/2.5.3)."""
    digits = ""
    for ch in text.strip():
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if not digits:
        return None
    value = int(digits)
    return value if 0 <= value <= scale else None


# --------------------------------------------------------------------------- #
# List elicitation (plan_benzon.md Part 4)
# --------------------------------------------------------------------------- #

#: The raw generation prompt itself — not a template that gets confidence
#: instructions baked in the way `build_phase0_prompt` does for every other
#: sentiment. List elicitation's Phase 0 asks for a plain list, nothing else;
#: the self-report (`sentiment.VARIETY`) is a separate Phase-1 question about
#: the list already generated, built generically by `build_confidence_prompt`
#: from `trial.question`/`trial.answer` like any other sentiment. The
#: brevity instruction is deliberate, not part of `plan_benzon.md`'s own
#: minimal template: an unconstrained Qwen generation reliably answers with
#: a paragraph-per-item ("**Tomato (Solanum lycopersicum)** — a popular
#: vegetable that is..."), which both truncates mid-item against any
#: reasonable `max_new_tokens` budget and defeats
#: `ground_truth.wordnet_category_membership`'s head-word check (the last
#: word of a whole paragraph is never the named item). Short items are a
#: precondition the rest of Part 4's pipeline actually needs, not a
#: cosmetic preference.
LIST_ELICITATION_TEMPLATE = "Give me a list of {n} {category}. Answer with just the {n} item names, no descriptions."

_NUMBERED_ITEM_RE = re.compile(r"^\s*(?:\d+[\.\)]|[-*•])\s*")


def parse_list_items(generation: str) -> list[str]:
    """Split a generated list into its individual items (plan_benzon.md Part 4).

    Handles the three shapes a list-elicitation generation realistically
    takes: numbered ("1. fox"), bulleted ("- fox" / "* fox" / "• fox"), and
    comma-separated on one line ("fox, wolf, and bear") — tried in that
    order, since a numbered/bulleted response is unambiguous the moment it
    spans more than one line, while a single-line response only makes sense
    read as a comma list. Trailing punctuation and a leading "and"/"or" from
    an English list's last item are stripped; blank lines are dropped.

    A model very often prefaces a numbered/bulleted list with a plain-text
    lead-in line ("Sure! Here is a list of 5 animals:") that is *not* itself
    a list item — when at least one line actually carries a numbered/bulleted
    marker, any unmarked line(s) before the first marked one are dropped as
    that lead-in, rather than counted as item zero.
    """
    text = generation
    for marker in (CONFIDENCE_CUE, "**Confidence**"):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]

    def _clean(piece: str) -> str:
        piece = _NUMBERED_ITEM_RE.sub("", piece).strip()
        piece = re.sub(r"^(and|or)\s+", "", piece, flags=re.IGNORECASE)
        return piece.strip(" .,;:\t")

    if len(lines) > 1:
        marked = [bool(_NUMBERED_ITEM_RE.match(line)) for line in lines]
        if any(marked):
            first_marked = marked.index(True)
            lines = lines[first_marked:]
        return [cleaned for line in lines if (cleaned := _clean(line))]

    line = _NUMBERED_ITEM_RE.sub("", lines[0]) if lines else ""
    return [cleaned for piece in line.split(",") if (cleaned := _clean(piece))]
