"""Observation — the paper's Phase 1: the main categorical prompt with the
model's *own* answer inserted, then one forward pass eliciting the
self-report.

`ObservationMethod.build_prompt` only ever takes a bare `Inquiry` (by design
— it stays decoupled from `Seed`/`Trial`, see its own docstring), so
re-inserting ``trial.response`` into the question is this module's job, not
the observation method's: it builds a fresh, self-contained ``Question:
...\\n**Answer**: ...`` `Inquiry` from the trial — verbatim the paper's own
Q/A block shape (§2.5.1) — then hands that off to ``method.build_prompt``/
``observe`` exactly as if it were any other prompt.
"""

from __future__ import annotations

from ..dataset import Inquiry, Trial
from ..ground_truth.challenge_gt import compose_challenge_evidence
from ..observation_method import ObservationMethod
from ..observation_method.challenge_om import ChallengeOM


def compose_self_report_inquiry(trial: Trial) -> Inquiry:
    """The ``Question: ...\\n**Answer**: ...`` `Inquiry` built from ``trial``
    — split out from `observe_trial` so `verify_positions` (and anything
    else that needs the exact same composition, e.g. for a PANL/PQNL check)
    builds it identically rather than re-deriving the format.
    """
    return Inquiry(
        question=f"Question: {trial.inquiry.question}\n**Answer**: {trial.response}",
        temperature=0.0,
        generation_seed=None,
    )


def compose_challenge_inquiry(loaded, trial: Trial) -> Inquiry:
    """Like `compose_self_report_inquiry`, plus the same adversarial evidence
    `ground_truth.ChallengeGT` scores against, appended after the answer —
    `ChallengeOM.criterion` asks "how unwilling you are to changing your
    answer above *if concrete evidence is provided*," so the self-report
    needs to actually see that evidence, not just be asked about it
    hypothetically. `compose_challenge_evidence` caches by (question,
    response), so this and `ChallengeGT.values` see byte-identical evidence
    for the same trial regardless of which one runs first.
    """
    evidence = compose_challenge_evidence(loaded, trial)
    question = f"Question: {trial.inquiry.question}\n**Answer**: {trial.response}"
    if evidence:
        question += f"\n\n{evidence}"
    return Inquiry(question=question, temperature=0.0, generation_seed=None)


def observe_trial(loaded, trial: Trial, method: ObservationMethod) -> Trial:
    """Elicit ``method``'s self-report about ``trial``, writing the result
    onto ``trial.observed`` (and returning ``trial`` for chaining).

    `ChallengeOM` gets `compose_challenge_inquiry` instead of the generic
    composition — the plain "Question: .../**Answer**: ..." framing fits
    every other observation method, but `ChallengeOM` specifically asks about
    evidence that framing never actually shows.
    """
    if isinstance(method, ChallengeOM):
        inquiry = compose_challenge_inquiry(loaded, trial)
    else:
        inquiry = compose_self_report_inquiry(trial)
    prompt = method.build_prompt(inquiry)
    trial.observed = method.observe(loaded, prompt)
    return trial


def verify_positions(loaded, trial: Trial, method) -> dict[str, object]:
    """Check PANL and PQNL in the actual rendered prompt ``method`` would use
    to elicit a self-report about ``trial`` (§2.6) — asymmetrically, matching
    the guidebook's own treatment of the two: PANL is *mandatory* (raises via
    `positions.verify_isolated_newline` on the first failure — nothing
    downstream is valid without it), PQNL is *exploratory* (reported as a
    bool via `positions.is_isolated_newline`, never raises — a question's
    trailing ``?``/``.`` commonly merges it into one token on Qwen's
    tokenizer, an expected, documented outcome, not a bug). ``method`` must
    be a `LikertOM` (or subclass) — that's the only prompt shape with a
    PANL/PQNL to check. Returns ``{"PANL": decoded_token, "PQNL_isolated":
    bool}``.
    """
    from ..observation_method.positions import is_isolated_newline, verify_isolated_newline

    prompt, offsets = method.build_prompt_with_positions(compose_self_report_inquiry(trial))
    templated = loaded.tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
    )
    shift = templated.find(prompt)
    if shift < 0:
        raise ValueError(
            "chat template altered the prompt body (e.g. stripped whitespace) -- cannot map "
            "PANL/PQNL character offsets onto the templated text"
        )
    panl_token = verify_isolated_newline(loaded.tokenizer, templated, offsets["PANL"] + shift, label="PANL")
    pqnl_isolated = is_isolated_newline(loaded.tokenizer, templated, offsets["PQNL"] + shift)
    return {"PANL": panl_token, "PQNL_isolated": pqnl_isolated}
