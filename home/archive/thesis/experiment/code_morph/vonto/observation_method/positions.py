"""Token-position verification for the paper's studied positions
(reproduction guidebook §2.5.1, §2.6) — the "mandatory setup checks" the
guidebook requires before trusting any downstream result:

- every self-report's classes must have distinct first tokens, or the
  argmax-over-class-ids read in `LikertOM.observe` can't tell them apart;
- PANL (the post-*answer* newline, right before the classification
  instructions) must be its own isolated token, not merged into the answer's
  last token or the instructions that follow;
- PQNL (the post-*question* newline, right before ``**Answer**:``) is the
  paper's own exploratory counterpart to PANL (studied for what information
  is available before the answer even exists) — the same isolation check
  applies to it, generically, via ``verify_isolated_newline``.
"""

from __future__ import annotations


def verify_class_tokens_unique(tokenizer, classes: tuple[str, ...], leading_space: bool = True) -> list[int]:
    """Assert every class's own first token is distinct under ``tokenizer``
    (§2.5.1, §13 #3). Returns the class-initial token ids, in ``classes``
    order, on success."""
    prefix = " " if leading_space else ""
    ids = [tokenizer(prefix + name, add_special_tokens=False)["input_ids"][0] for name in classes]
    if len(set(ids)) != len(classes):
        raise ValueError(
            f"class-initial tokens collide under this tokenizer: {dict(zip(classes, ids))} — "
            "the argmax read in LikertOM.observe can't distinguish these classes"
        )
    return ids


def _token_at_offset(offsets: list[tuple[int, int]], char_index: int) -> int:
    for i, (start, end) in enumerate(offsets):
        if start <= char_index < end:
            return i
    raise ValueError(f"no token covers character offset {char_index}")


def verify_isolated_newline(tokenizer, text: str, char_index: int, label: str = "position") -> str:
    """Assert the newline at ``text[char_index]`` is its own token: it must
    start exactly there (not merged into preceding content, e.g. an answer
    ending in punctuation producing a ``".\\n"`` token) and decode to pure
    whitespace beginning with ``"\\n"`` (not merged with what follows either,
    e.g. a blank-line ``"\\n\\n"`` token). Returns the decoded token on
    success; raises with ``label`` in the message on failure — the same
    structural check the paper requires for both PANL and PQNL (§2.6),
    neither of which is a meaningful studied position if the tokenizer has
    merged it into a neighbor.
    """
    if text[char_index] != "\n":
        raise ValueError(f"text[{char_index}] is {text[char_index]!r}, not a newline ({label})")
    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = [tuple(o) for o in enc["offset_mapping"]]
    index = _token_at_offset(offsets, char_index)
    token = tokenizer.decode([enc["input_ids"][index]])
    if token.strip() != "" or not token.startswith("\n"):
        raise ValueError(
            f"{label} is not an isolated whitespace token (decoded {token!r}) — the position "
            "semantics of any study of this position break (§2.6)"
        )
    if offsets[index][0] != char_index:
        raise ValueError(
            f"{label} is merged into the preceding token (token starts at {offsets[index][0]}, "
            f"not {char_index}) — the position semantics of any study of this position break (§2.6)"
        )
    return token


def is_isolated_newline(tokenizer, text: str, char_index: int) -> bool:
    """Non-raising counterpart to `verify_isolated_newline` — for PQNL, which
    the guidebook treats as *exploratory* rather than mandatory: on Qwen's
    tokenizer a question's trailing ``?``/``.`` commonly merges with the
    following newline into one token (``"?\\n"``), so most naturally-phrased
    questions are *expected* to fail this, not a bug to raise on (unlike
    PANL, which must hold for every trial or nothing downstream is valid).
    """
    try:
        verify_isolated_newline(tokenizer, text, char_index, label="PQNL")
        return True
    except ValueError:
        return False
