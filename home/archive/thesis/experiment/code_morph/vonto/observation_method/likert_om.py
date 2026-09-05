"""Shared machinery for every N-way categorical self-report (confidence,
commitment, nuance, ...) — not itself one of the requested observation
methods, just the common base `ConfidenceOM`/`CommitmentOM`/`NuanceOM` share,
so each of those stays a short list of ``name``/``criterion``/``classes``
instead of re-deriving the same prompt/logit-reading logic three times.

Prompt shape and read mechanism reproduce the paper's own Phase-1 categorical
prompt (reproduction guidebook §2.5.1) rather than an ad-hoc equivalent:
the framing header, the per-class numeric ranges, and — the part that
actually matters for *which token gets read* — a forced completion cue.
``build_prompt`` returns everything up to (not including) the cue; ``observe``
chat-templates that as the user turn, then appends the literal cue string
(``"**Confidence**:"``, etc.) directly onto the templated text before
encoding, exactly as `archive/vconf/models.py:render_prompt` does
(``templated + suffix``) — so the model's assistant turn is *prefilled*
starting mid-cue, and the very next token is read at that forced position,
not at the free-form start of a fresh turn. Reading logits there (rather than
generating) is valid only because the ten confidence classes were engineered
to have distinct first tokens (§2.5.1); every subclass here inherits that
same one-forward-pass mechanism regardless of what its own classes are.
"""

from __future__ import annotations

from ..dataset import Inquiry
from .observation_method import ObservationMethod

#: Paper's own framing sentence (§2.5.1), prepended verbatim ahead of the
#: question/answer block — construct-agnostic, so every `LikertOM` subclass
#: shares it rather than re-authoring their own.
HEADER = "You will be shown a question, together with an answer you previously provided before.\n\n"

#: Shared 10-point intensity ladder — every construct here except
#: `ConfidenceOM` (whose own 10-class scale is the paper's verbatim wording,
#: §2.5.1, and must stay exactly as written, not templated) builds its
#: `classes` from this via `intensity_classes`, so every self-report in
#: vonto shares the same category count and framing style the paper uses for
#: confidence, instead of each construct inventing its own N and wording.
#: First words are pairwise tokenizer-distinct (verified against
#: Qwen2.5-7B-Instruct) — the same §2.5.1/§13 #3 requirement `ConfidenceOM`'s
#: own class list satisfies, needed for `LikertOM.observe`'s argmax read to
#: mean anything at all.
INTENSITY_LADDER: tuple[str, ...] = (
    "Not", "Barely", "Slightly", "Somewhat", "Moderately",
    "Fairly", "Quite", "Very", "Highly", "Extremely",
)


def intensity_classes(adjective: str) -> tuple[str, ...]:
    """10 classes, low -> high, of the form ``"{intensifier} {adjective}"``
    — the lowest reads ``"Not {adjective} at all"`` for a natural low pole."""
    return tuple(
        f"Not {adjective} at all" if word == "Not" else f"{word} {adjective}"
        for word in INTENSITY_LADDER
    )


class LikertOM(ObservationMethod):
    """One N-way Likert-scale self-report: ``classes`` ordered low -> high,
    ``criterion`` completing "based on ...". ``observe`` reads the model's
    logits at each class's own first token (a single forward pass, no
    generation) and returns ``(winning_class, its_midpoint)``.

    **Constraint this relies on but does not itself check** (reproduction
    guidebook §2.5.1, §13 #3): ``classes`` must have pairwise-distinct first
    tokens under the tokenizer actually in use, or the ``argmax`` in
    ``observe`` can't tell two classes apart — a genuine tokenizer-dependent
    fact, not something guaranteed by the class *names* alone, so verify it
    per subclass, per tokenizer, before trusting any of its results:
    ``vonto.observation_method.positions.verify_class_tokens_unique(tokenizer,
    om.classes)``. All six concrete subclasses pass under Qwen2.5-7B-Instruct's
    tokenizer (checked directly, not merely assumed) — that does not
    generalize to a different tokenizer without re-checking.

    **Constraint the *read position* relies on** (§2.6): PANL — the newline
    ``build_prompt_with_positions`` places between the question/answer block
    and the classification instructions — must be its own isolated token for
    the position semantics to mean what the guidebook says they mean; it
    fails to be isolated whenever the answer text itself ends in punctuation
    (the trailing character merges into a single ``".\\n"`` token instead).
    This is mandatory, not exploratory, and not self-enforcing here — verify
    per trial with `vonto.calibration.observation.verify_positions`, which
    raises on a PANL failure by design (nothing downstream is valid without
    it) but only *reports* the analogous PQNL (post-question newline) check,
    since that one is the guidebook's own exploratory counterpart to PANL and
    is *expected* to fail on most naturally-phrased questions (a trailing
    ``?``/``.`` merges the same way). Neither check runs automatically as
    part of `observe`/`calibration.generate_trials` — a caller who cares
    about position-level validity (as opposed to just the aggregate self-
    report value) must run it explicitly.
    """

    name: str
    criterion: str
    classes: tuple[str, ...]
    #: The paper's own sentence for confidence specifically is "Each category
    #: reflects the probability that the answer is correct." (§2.5.1) —
    #: `ConfidenceOM` overrides this to that exact wording; every other
    #: construct here has no such paper-defined sentence, so this generic one
    #: describes its own evenly spaced numeric scale instead.
    range_description: str = "Each category reflects a range along this scale."

    @property
    def class_midpoints(self) -> dict[str, float]:
        n = len(self.classes)
        return {c: round((i + 0.5) / n, 3) for i, c in enumerate(self.classes)}

    @property
    def class_ranges(self) -> dict[str, tuple[float, float]]:
        """Each class's own ``[lo, hi)`` bound, evenly dividing ``[0, 1]`` —
        for the paper's own 10-class confidence scale this reproduces its
        exact canonical ranges (``0.0-0.1``, ``0.1-0.2``, ..., ``0.9-1.0``,
        §2.5.1) for free, since those are themselves just even tenths."""
        n = len(self.classes)
        return {c: (round(i / n, 3), round((i + 1) / n, 3)) for i, c in enumerate(self.classes)}

    @property
    def instructions(self) -> str:
        """The classification instructions alone (no header, no question) —
        split out from `build_prompt` so `calibration.generation` can reuse
        the exact same text, front-loaded, for the paper's Phase-0 prompt
        (reproduction guidebook §2.4), which always uses this same
        instruction block regardless of what's later asked in Phase 1."""
        class_list = "\n".join(f'- "{c}" ({lo:.1f}-{hi:.1f})' for c, (lo, hi) in self.class_ranges.items())
        return (
            f"Classify your {self.name} into one of the following classes based on "
            f"{self.criterion} (NO REASONING OR EXPLANATION):\n\n{class_list}\n\n"
            f"{self.range_description}\n\n"
            f"At the very end of your output, format your {self.name} as\n"
            f"**{self.name.capitalize()}**: $CLASS\n"
            "where CLASS is one of the names (only the names without the ranges) of the classes above."
        )

    def build_prompt(self, inquiry: Inquiry) -> str:
        text, _ = self.build_prompt_with_positions(inquiry)
        return text

    def build_prompt_with_positions(self, inquiry: Inquiry) -> tuple[str, dict[str, int]]:
        """Like `build_prompt`, plus the character offsets of PQNL (the
        newline right after the question, before ``**Answer**:``) and PANL
        (the newline right after the question/answer block, before the
        classification instructions — a single newline, matching the paper's
        own literal template character-for-character, §2.5.1). Both are
        found structurally rather than passed in: `calibration.observation`
        always composes ``inquiry.question`` as
        ``"Question: ...\\n**Answer**: ..."`` for every self-report
        elicitation, so this raises ``ValueError`` (via ``str.index``) if
        handed an ``inquiry`` that wasn't built that way — a bare dataset
        `Inquiry` has no PQNL/PANL to find, so failing loudly here is
        correct, not a bug to work around.
        """
        text = f"{HEADER}{inquiry.question}\n{self.instructions}"
        panl_offset = len(HEADER) + len(inquiry.question)
        pqnl_offset = len(HEADER) + inquiry.question.index("\n**Answer**:")
        return text, {"PQNL": pqnl_offset, "PANL": panl_offset}

    def observe(self, loaded, prompt: str) -> tuple[str, float]:
        import torch

        cue = f"**{self.name.capitalize()}**:"
        text = loaded.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )
        text += cue
        enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
        class_ids = [loaded.tokenizer(" " + c, add_special_tokens=False)["input_ids"][0] for c in self.classes]
        with torch.no_grad():
            logits = loaded.model(**enc).logits[0, -1]
        winner = self.classes[int(logits[class_ids].argmax())]
        return winner, self.class_midpoints[winner]
