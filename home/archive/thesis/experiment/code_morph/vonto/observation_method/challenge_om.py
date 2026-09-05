"""Challenge: how resistant the model is to changing its answer once shown
adversarial evidence against it. Reproduces
`archive/vconf/commitment_challenge.py`'s behavioral protocol (dynamic
evidence vs. counterfeit evidence), decoupled here into a self-report half
(this OM) and a computed half (`ground_truth.ChallengeGT`).

Composing the actual challenge — picking genuine vs. generated-counterfeit
evidence and rendering it alongside the original question/answer — is
`ground_truth.ChallengeGT`'s job, not this OM's: by the time this OM ever
sees a prompt, that composition has already happened and landed in
``inquiry.question``, keeping `observe` just as modular as every other
observation method (a loaded model plus an already-built prompt string,
nothing Seed/Trial-specific)."""

from __future__ import annotations

from .likert_om import LikertOM, intensity_classes


class ChallengeOM(LikertOM):
    name = "challenge"
    #: Low -> high == "not unwilling" (changes easily) -> "extremely unwilling"
    #: (defends), matching the direction `ground_truth.ChallengeGT`'s own
    #: logit-margin score uses (higher = more unwilling), so a well-
    #: calibrated self-report correlates *positively* with it, the same as
    #: every other OM/GT pair here.
    tags = ["baseline", "general", "caves", "defends"]
    criterion = (
        "how unwilling you are to changing your answer above if conctrete evidence is provided "
        "that argues otherwise"
    )
    classes: tuple[str, ...] = intensity_classes("unwilling")
