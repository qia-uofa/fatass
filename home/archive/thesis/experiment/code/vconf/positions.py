"""Locating the studied token positions per trial (§2.6).

Positions are *never* hard-coded offsets: each prompt is tokenised once with an
offset mapping, and the character spans recorded by :mod:`vconf.prompts` are
translated into token indices.  The functions that do the translating are pure
(they take an offset mapping, not a tokenizer) so they can be unit-tested with
synthetic inputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .prompts import BuiltPrompt

#: The positions defined in §2.6.
POSITION_NAMES = (
    "AC", "first A", "last A", "PANL", "PANL+1", "FCC", "CC", "QTT",
)


class PositionError(ValueError):
    """Raised when a studied position cannot be isolated in the tokenisation."""


def char_to_token(offsets: list[tuple[int, int]], char_idx: int) -> int:
    """Index of the token whose character span contains ``char_idx``."""
    for i, (start, end) in enumerate(offsets):
        if start <= char_idx < end:
            return i
    raise PositionError(f"no token covers character {char_idx}")


def span_to_tokens(offsets: list[tuple[int, int]], span: tuple[int, int]) -> tuple[int, int]:
    """``(first_token, last_token)`` (inclusive) covering a character span."""
    start, end = span
    first = char_to_token(offsets, start)
    last = char_to_token(offsets, max(start, end - 1))
    return first, last


def locate_positions(
    offsets: list[tuple[int, int]],
    spans: dict[str, tuple[int, int]],
    n_tokens: int | None = None,
) -> dict[str, int]:
    """Translate the character spans of a built prompt into token indices.

    Only the positions whose spans are present are returned; ``CC`` is always
    the very last token of the prompt (§2.6), and ``PANL+1`` the token right
    after ``PANL``.
    """
    n_tokens = n_tokens if n_tokens is not None else len(offsets)
    positions: dict[str, int] = {}

    if "PANL" in spans:
        panl = char_to_token(offsets, spans["PANL"][0])
        positions["PANL"] = panl
        if panl + 1 >= n_tokens:
            raise PositionError("PANL is the final token; PANL+1 does not exist")
        positions["PANL+1"] = panl + 1
    if "FCC" in spans:
        positions["FCC"] = char_to_token(offsets, spans["FCC"][0])
    if "AC" in spans:
        positions["AC"] = char_to_token(offsets, spans["AC"][0])
    if "answer" in spans:
        first, last = span_to_tokens(offsets, spans["answer"])
        positions["first A"] = first
        positions["last A"] = last
    if "question" in spans:
        q_first, q_last = span_to_tokens(offsets, spans["question"])
        qtt = q_first + 2  # third question token (§2.6)
        if qtt > q_last:
            raise PositionError("question is shorter than three tokens; QTT undefined")
        positions["QTT"] = qtt
    if "CC" in spans:
        positions["CC"] = n_tokens - 1
    return positions


def trace_positions(
    offsets: list[tuple[int, int]], span: tuple[int, int], n_points: int = 10
) -> dict[str, int]:
    """Magistral ``Trace k%`` positions: tokens at 10% increments of the trace (§12.4).

    ``Trace 100%`` is the last token of the trace.
    """
    first, last = span_to_tokens(offsets, span)
    length = last - first
    out: dict[str, int] = {}
    for k in range(1, n_points + 1):
        frac = k / n_points
        out[f"Trace {int(frac * 100)}%"] = first + int(round(length * frac))
    return out


@dataclass
class RenderedPrompt:
    """A prompt as actually fed to the model, with token indices resolved."""

    text: str
    input_ids: list[int]
    offsets: list[tuple[int, int]]
    positions: dict[str, int]
    spans: dict[str, tuple[int, int]]
    kind: str = "categorical"
    phase: int = 1

    @property
    def n_tokens(self) -> int:
        return len(self.input_ids)

    def token_text(self, name: str, tokenizer) -> str:
        return tokenizer.decode([self.input_ids[self.positions[name]]])


def remap_spans(
    spans: dict[str, tuple[int, int]],
    cut: int,
    head_len: int,
    rendered_len: int,
    original_len: int,
) -> dict[str, tuple[int, int]]:
    """Shift character spans from a raw prompt onto its chat-templated rendering.

    The rendering is ``head + prompt[:cut] + tail + prompt[cut:]``: everything
    before ``cut`` shifts by ``head_len``, everything at/after ``cut`` sits at
    the very end of the rendered string.
    """
    out: dict[str, tuple[int, int]] = {}
    for name, (start, end) in spans.items():
        if end <= cut:
            out[name] = (start + head_len, end + head_len)
        else:
            out[name] = (
                rendered_len - (original_len - start),
                rendered_len - (original_len - end),
            )
    return out


def cue_cut(built: BuiltPrompt) -> int:
    """Character index where the assistant-prefilled cue of a prompt starts.

    The cue is the fragment the model is meant to continue — ``**Confidence**:``
    (categorical / numeric / Magistral), ``**State Confidence(0-9) with NO
    SPACE**:'`` (minimal numeric) or ``**Answer**:`` (Phase 0).  Keeping it out
    of the user turn is what makes CC (respectively AC) the *last token of the
    prompt*, as §2.6 requires.
    """
    from .prompts import ANSWER_CUE, CONFIDENCE_CUE, MINIMAL_CUE

    if built.phase == 0:
        if built.kind == "magistral":
            return len(built.text)
        return len(built.text) - len(ANSWER_CUE)
    if built.kind == "minimal_numeric":
        return len(built.text) - len(MINIMAL_CUE)
    return len(built.text) - len(CONFIDENCE_CUE)
