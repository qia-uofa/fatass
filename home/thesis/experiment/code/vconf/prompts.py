"""Verbatim prompt templates (§2.5) and the confidence-class table (§2.5.1).

The templates are reproduced character-for-character from the manual, including
the en-dashes in the probability ranges and the trailing apostrophe of the
minimal numeric prompt.  Every builder returns a :class:`BuiltPrompt` carrying
the prompt text *plus the character spans* of the positions the paper studies,
so that token indices can be recovered per trial by tokenisation (§2.6) instead
of being hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Confidence classes and their midpoints (§2.5.1)
# --------------------------------------------------------------------------- #

CLASSES: tuple[str, ...] = (
    "No chance",
    "Really unlikely",
    "Chances are slight",
    "Unlikely",
    "Less than even",
    "Better than even",
    "Likely",
    "Very good chance",
    "Highly likely",
    "Almost certain",
)

CLASS_RANGES: dict[str, tuple[float, float]] = {
    "No chance": (0.0, 0.1),
    "Really unlikely": (0.1, 0.2),
    "Chances are slight": (0.2, 0.3),
    "Unlikely": (0.3, 0.4),
    "Less than even": (0.4, 0.5),
    "Better than even": (0.5, 0.6),
    "Likely": (0.6, 0.7),
    "Very good chance": (0.7, 0.8),
    "Highly likely": (0.8, 0.9),
    "Almost certain": (0.9, 1.0),
}

CLASS_MIDPOINT: dict[str, float] = {
    name: round((lo + hi) / 2, 2) for name, (lo, hi) in CLASS_RANGES.items()
}

#: Top three classes (§2.5.1).
HIGH_BAND: tuple[str, ...] = ("Very good chance", "Highly likely", "Almost certain")
#: Bottom three classes (§2.5.1).
LOW_BAND: tuple[str, ...] = ("No chance", "Really unlikely", "Chances are slight")

#: Qwen's narrower distribution uses adjacent-but-separated classes (§2.7).
QWEN_HIGH_BAND: tuple[str, ...] = ("Likely",)
QWEN_LOW_BAND: tuple[str, ...] = ("Unlikely",)

#: Steering-vector extraction poles (§4.2).
HIGHEST_CLASS = "Almost certain"
LOWEST_CLASS = "No chance"


def bands(model_key: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(high band, low band) for a model, applying the Qwen adjustment (§2.7)."""
    if model_key == "qwen":
        return QWEN_HIGH_BAND, QWEN_LOW_BAND
    return HIGH_BAND, LOW_BAND


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


def _qa_block(question: str, answer: str) -> tuple[str, dict[str, tuple[int, int]]]:
    """``Question: {q}\\n**Answer**: {a}`` with the question/answer spans."""
    prefix = "Question: "
    text = prefix + question
    q_span = (len(prefix), len(text))
    text += "\n" + ANSWER_CUE
    ac_span = (len(text) - 1, len(text))  # the answer-colon (§2.6)
    text += " "
    a_start = len(text)
    text += answer
    a_span = (a_start, len(text))
    return text, {"question": q_span, "answer": a_span, "AC": ac_span}


def build_confidence_prompt(question: str, answer: str, kind: str = "categorical") -> BuiltPrompt:
    """Build the Phase-1 confidence prompt for one trial (§2.5.1–2.5.3)."""
    if kind == "categorical":
        head = CATEGORICAL_HEADER
        body, spans = _qa_block(question, answer)
        text = head + body
        spans = {k: (s + len(head), e + len(head)) for k, (s, e) in spans.items()}
        panl_start = len(text)
        text += "\n"
        spans["PANL"] = (panl_start, panl_start + 1)
        instr_start = len(text)
        text += CATEGORICAL_INSTRUCTIONS
        fcc = instr_start + CATEGORICAL_INSTRUCTIONS.index(CONFIDENCE_CUE) + len(CONFIDENCE_CUE)
        spans["FCC"] = (fcc - 1, fcc)
        text += "\n\n" + CONFIDENCE_CUE
        spans["CC"] = (len(text) - 1, len(text))
        return BuiltPrompt(text=text, spans=spans, kind=kind, phase=1)

    if kind == "numeric":
        head = NUMERIC_HEADER
        body, spans = _qa_block(question, answer)
        text = head + body
        spans = {k: (s + len(head), e + len(head)) for k, (s, e) in spans.items()}
        panl_start = len(text)
        text += "\n"
        spans["PANL"] = (panl_start, panl_start + 1)
        instr_start = len(text)
        text += NUMERIC_INSTRUCTIONS
        fcc = instr_start + NUMERIC_INSTRUCTIONS.index(CONFIDENCE_CUE) + len(CONFIDENCE_CUE)
        spans["FCC"] = (fcc - 1, fcc)
        text += "\n" + CONFIDENCE_CUE
        spans["CC"] = (len(text) - 1, len(text))
        return BuiltPrompt(text=text, spans=spans, kind=kind, phase=1)

    if kind == "minimal_numeric":
        head = MINIMAL_HEADER
        body, spans = _qa_block(question, answer)
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


def build_phase0_prompt(question: str, kind: str = "categorical") -> BuiltPrompt:
    """Phase-0 answer-generation prompt (§2.4, §13 #12).

    The confidence-instruction block is moved to the *start* and the prompt ends
    at ``**Answer**:`` — whose colon is the answer-colon (AC) position.
    """
    if kind in ("categorical", "minimal_numeric", "magistral"):
        # The minimal numeric prompt (§2.5.3) has no instruction block of its own
        # to move — it is a confidence-elicitation cue only — so Phase 0 uses the
        # canonical §13 #12 prompt, which also yields a Phase-0 confidence class.
        instructions, head = CATEGORICAL_INSTRUCTIONS, CATEGORICAL_HEADER
    elif kind == "numeric":
        instructions, head = NUMERIC_INSTRUCTIONS.lstrip("\n"), NUMERIC_HEADER
    else:
        raise KeyError(f"unknown prompt kind: {kind!r}")

    text = instructions + "\n\n" + head
    q_prefix = "Question: "
    text += q_prefix
    q_start = len(text)
    text += question
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


def build_magistral_confidence_prompt(question: str, trace: str, answer: str) -> BuiltPrompt:
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
    text += MAGISTRAL_INSTRUCTIONS
    fcc = instr_start + MAGISTRAL_INSTRUCTIONS.index(CONFIDENCE_CUE) + len(CONFIDENCE_CUE)
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


def parse_class(text: str) -> str | None:
    """Return the confidence class named in ``text`` (longest match wins)."""
    stripped = text.strip().strip('"')
    for name in sorted(CLASSES, key=len, reverse=True):
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
