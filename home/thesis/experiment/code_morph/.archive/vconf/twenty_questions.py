"""Multi-turn 20-Questions sessions (plan_benzon.md Part 5).

The two-phase protocol (:mod:`vconf.pipeline`) has no notion of multi-turn
state — every other Benzon part (Parts 2-4) is a bespoke dataset/sentiment
pair layered on top of the existing single-turn machinery unchanged. This is
the one piece that needs genuinely new infrastructure.

**Two question-generation designs, both provided:**

- `NEXT_QUESTION_PROMPT`/`build_next_question_prompt`/`TwentyQuestionsSession` —
  ``plan_benzon.md``'s own literal spec: deliberately stateless beyond an
  injected ``remaining`` set re-stated every turn, not a growing chat
  transcript, to avoid context-length blowup. Kept here and tested, but
  *not* what the notebook actually plays: it hands the model the harness's
  own internal, ground-truth candidate pool every turn, which it never
  actually earned by asking anything.
  `notebooks_benzon/phase_0_calibration/5_twenty_questions.ipynb` found this hint made the
  self-report/impurity comparison substantially less meaningful — the model
  isn't really playing the game it's being scored on.
- `INITIAL_QUESTION_PROMPT`/`build_conversation_for_next_question`/
  `transcript_summary` — the realistic alternative the notebook actually
  plays: the keyword universe is shown exactly **once**, in the first
  message; every later question-generation call replays the model's own
  prior questions and the harness's truthful "Yes"/"No" replies to them as a
  real, growing chat history, so the model has to track what's already been
  asked/eliminated itself, the way an actual 20-questions player does,
  rather than being told directly. The harness still tracks the true
  candidate pool internally (needed to compute `metrics.gini_impurity` and
  to answer truthfully) — that bookkeeping is simply never shown to the
  model.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

import numpy as np

#: Ten WordNet noun categories for per-category keyword universes (e.g. 10
#: categories × 10 games each × 10 turns = 1000 trials): 7 concrete
#: (physical-referent) categories followed by 3 abstract ones, so a
#: concreteness split (`ABSTRACT_CATEGORIES`) is available for a
#: concrete-vs-abstract rho comparison, not just an aggregate one. Each has a
#: comfortable margin of qualifying Brown common nouns (193-883, checked
#: against the same NN/NNS/len>=3 filter `sample_natural_keywords` applies)
#: above the 100-word universes actually drawn per game, so 10
#: independently-seeded per-game samples never run out of unique candidates
#: to draw without replacement — though for the smaller categories here
#: (e.g. "emotion.n.01", 193 members), different games' 100-word draws still
#: overlap substantially, since there's only ~2x headroom to draw from.
CATEGORIES: tuple[str, ...] = (
    # concrete (7)
    "animal.n.01", "plant.n.02", "food.n.01", "body_part.n.01", "vehicle.n.01",
    "structure.n.01", "container.n.01",
    # abstract (3)
    "emotion.n.01", "cognition.n.01", "attribute.n.02",
)

#: The 3 categories in `CATEGORIES` with no physical referent — a keyword
#: from one of these (a feeling, a thought, a quality) can't be pointed at,
#: unlike a keyword from any of the other 7 (an animal, a vehicle, a body
#: part, ...). Used to split trials into a concrete-vs-abstract rho
#: comparison alongside the aggregate one.
ABSTRACT_CATEGORIES: tuple[str, ...] = ("emotion.n.01", "cognition.n.01", "attribute.n.02")


@functools.lru_cache(maxsize=1)
def _brown_noun_counts() -> dict[str, int]:
    """Common-noun (``NN``/``NNS``) token frequency counts from the Brown
    corpus. Cached process-wide: `sample_natural_keywords` is called once per
    game (up to 100 times for a full categorized run), and re-scanning
    Brown's 1.16M tokens on every call would be pure waste.
    """
    import nltk

    try:
        nltk.data.find("corpora/brown")
    except LookupError:
        nltk.download("brown", quiet=True)
    from nltk.corpus import brown

    counts: dict[str, int] = {}
    for word, tag in brown.tagged_words():
        # len(word) >= 3 excludes single/double-letter abbreviation artifacts
        # ("b", "af", "cm") that Brown's tagger still labels NN/NNS — not
        # genuine English words, just noise the frequency weighting would
        # otherwise treat as legitimate low-frequency nouns.
        if tag in ("NN", "NNS") and word.isalpha() and len(word) >= 3:
            lw = word.lower()
            counts[lw] = counts.get(lw, 0) + 1
    return counts


@functools.lru_cache(maxsize=None)
def _category_members(category: str) -> tuple[str, ...]:
    """Which of `_brown_noun_counts`'s words have ``category`` (a WordNet
    noun synset name, e.g. ``"animal.n.01"``) as one of their noun senses, or
    a hyponym of it. Cached per category for the same reason
    `_brown_noun_counts` is cached — a categorized run calls this once per
    game, not once overall.
    """
    import nltk

    try:
        from nltk.corpus import wordnet as wn

        wn.synsets("test")
    except LookupError:
        nltk.download("wordnet", quiet=True)
        from nltk.corpus import wordnet as wn

    target = wn.synset(category)
    members = set(target.closure(lambda s: s.hyponyms()))
    members.add(target)
    return tuple(
        w for w in _brown_noun_counts() if any(syn in members for syn in wn.synsets(w, pos=wn.NOUN))
    )


def sample_natural_keywords(n: int = 100, seed: int = 0, category: str | None = None) -> tuple[str, ...]:
    """Sample ``n`` unique English common nouns for the keyword universe,
    weighted by their natural occurrence frequency in written English (the
    Brown corpus — a genre-balanced sample of American English) rather than
    a hand-picked category list (an earlier version of this notebook used a
    curated 100-animal list).

    Restricted to common-noun tokens (Brown tags ``NN``/``NNS``): raw,
    part-of-speech-unrestricted word frequency in English text is dominated
    by function words ("the", "of", "and", ...) — sampling from the full,
    unrestricted vocabulary by frequency would return mostly those, which
    can't support a yes/no 20-questions game (there's no meaningful "is your
    keyword an animal?" for "the"). Sampling is without replacement (no
    repeats) and weighted, not uniform and not simply the ``n`` most
    frequent words either: a rare noun can still be drawn, just less often
    than a common one, mirroring how the words actually occur in natural
    text. ``seed`` makes the sample reproducible.

    ``category``, when given, is a WordNet noun synset name (see
    `CATEGORIES`) restricting the candidate pool to Brown nouns that are (a
    sense of) that synset or one of its hyponyms — the sample stays
    frequency-weighted and non-repeating, just drawn from one semantic
    category instead of the full English noun vocabulary.
    """
    counts = _brown_noun_counts()
    words = list(_category_members(category)) if category is not None else list(counts)
    weights = np.array([counts[w] for w in words], dtype=float)
    weights /= weights.sum()
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(words), size=n, replace=False, p=weights)
    return tuple(sorted(words[i] for i in chosen))


NEXT_QUESTION_PROMPT = (
    "here is a list of keywords:\n{keywords}\n\n"
    "you are playing 20 questions, some keywords have been eliminated by your "
    "former questions. the remaining ones are: {remaining}.\n\n"
    "Ask the next question."
)

#: The game's own rules, shared verbatim by two very different callers: it's
#: the very first message of the actual game conversation (via
#: `INITIAL_QUESTION_PROMPT` below, which just appends "Ask your first
#: question." to it) *and* the context `transcript_summary` restates for the
#: `IMPURITY` self-report call, so that call reasons with the same rules the
#: model had while actually playing, not a stripped-down summary of them.
#: Nothing here (or in any later turn) tells the model which keywords are
#: still live; it has to infer that itself from its own memory of the
#: conversation. The explicit phrasing rule ("Is your keyword ...?", not "Is
#: your secret keyword ...?") is deliberate, not decorative: an
#: unconstrained generation reliably drifted into the clunkier, redundant
#: "secret" wording. A concrete worked example was tried first (e.g. "Is
#: your keyword an animal?") but backfired badly on a homogeneous keyword
#: universe (all animals here): the model just copied the example verbatim
#: as its real first question, which is uninformative by construction
#: whenever every keyword shares that property — stalling every session on
#: turn one. Stating the phrasing rule abstractly, with no concrete question
#: the model could parrot, avoids that trap while still fixing the "secret"
#: wording. The binary-search strategy sentence is spelled out explicitly
#: (rather than left for the model to discover) for the same reason
#: `PARTITION_PROMPT`'s output-format line is explicit: an unprompted model
#: has no particular reason to prefer maximally-informative questions over
#: merely-valid ones, and the whole point of `IMPURITY`'s self-report is to
#: judge how well it follows that strategy turn to turn.
GAME_RULES_TEMPLATE = (
    "Here is a list of {n} keywords:\n{keywords}\n\n"
    "I have a secret keyword in mind from that list. You are playing 20 questions to "
    'figure out which one it is — ask yes/no questions about it, one at a time, always '
    'phrased as "Is your keyword <some property>?" (not "Is your secret keyword ...?"). '
    "A good strategy is to perform a binary search: try to ask a question that would "
    "eliminate roughly half of whatever keywords are still possible, since that narrows "
    "down the possibilities fastest."
)

#: `GAME_RULES_TEMPLATE` plus the one instruction that only makes sense as
#: the very first message of a real game conversation — never repeated
#: after turn zero (see `build_conversation_for_next_question`).
INITIAL_QUESTION_PROMPT = GAME_RULES_TEMPLATE + " Ask your first question."

#: Appended after the harness's truthful "Yes"/"No" reply on every later
#: turn. The elimination-framing sentence reinforces the same binary-search
#: strategy from `GAME_RULES_TEMPLATE` without naming an actual count or set
#: of eliminated keywords — that bookkeeping stays internal to the harness
#: (see the module docstring); this is a fixed reminder of the *goal*, not a
#: progress report.
_NEXT_TURN_SUFFIX = (
    "\n\nYou have eliminated some of the keywords with that answer. Ask your next "
    "question — ideally one that eliminates roughly half of whatever keywords remain."
)


def build_conversation_for_next_question(
    keywords: tuple[str, ...], qa_history: list[tuple[str, str]]
) -> list[dict[str, str]]:
    """Chat messages for generating the *next* question, ending right where the
    model's own next turn should begin — pass straight to
    ``tokenizer.apply_chat_template(messages, add_generation_prompt=True)``.

    The keyword universe appears exactly once, as the first user turn; every
    question the model has already asked becomes its own assistant turn,
    immediately followed by the harness's truthful "Yes"/"No" reply as the
    next user turn — a real, growing conversation, not a flat re-stated
    prompt. ``qa_history`` is exactly what the model itself has already
    seen, nothing more: no internal "remaining" bookkeeping leaks in here.
    """
    messages = [{
        "role": "user",
        "content": INITIAL_QUESTION_PROMPT.format(n=len(keywords), keywords=format_keywords(keywords)),
    }]
    for question, answer in qa_history:
        messages.append({"role": "assistant", "content": question})
        messages.append({"role": "user", "content": f"{answer}{_NEXT_TURN_SUFFIX}"})
    return messages


def transcript_summary(keywords: tuple[str, ...], qa_history: list[tuple[str, str]]) -> str:
    """A plain-text restatement of exactly what the model actually had access
    to when it asked its most recent question: the same `GAME_RULES_TEMPLATE`
    (full keyword list, phrasing rule, and binary-search strategy) the model
    saw as its very first game message, plus every prior ``(question,
    answer)`` pair it has since seen. Used as `sentiment.IMPURITY`'s
    self-report "question" field.

    Deliberately *not* a stripped-down summary any more — an earlier version
    gave only the keyword count, on the theory that repeating the list would
    "leak" information. It didn't: the model already saw the full list once,
    during the game itself (`build_conversation_for_next_question`), so
    restating it here for the self-report call leaks nothing it doesn't
    already know — it only withholds context the self-report needs to judge
    "how evenly did this split the keywords" against the same rules and
    universe the question was actually asked over. The harness's own
    internal "remaining" set is still never named, here or anywhere else.
    """
    rules = GAME_RULES_TEMPLATE.format(n=len(keywords), keywords=format_keywords(keywords))
    if not qa_history:
        return rules
    lines = "; ".join(f'Q{i + 1}: "{q}" -> {a}' for i, (q, a) in enumerate(qa_history))
    return f"{rules} So far: {lines}."

#: Batched partition-grading prompt (plan_benzon.md Part 5 step 2) — one call
#: per turn instead of one call per remaining keyword (the naive, far more
#: expensive alternative). Ends with an explicit output-format instruction so
#: `parse_partition` has a fixed shape to parse, same convention as every
#: other structured-output prompt in this codebase (``**Confidence**:``,
#: ``**Answer**:``). "(NO REASONING OR EXPLANATION)" is deliberate, not
#: decorative — reused verbatim from `prompts.CATEGORICAL_INSTRUCTIONS`'s own
#: convention: an unconstrained Qwen generation reliably walks through each
#: keyword's reasoning *before* the final ``**Yes**:`` line, which burns a
#: generation-length budget that's supposed to cover only that one line and
#: silently truncates it mid-list — exactly the kind of corrupted ground
#: truth that's worse than an obviously-failed parse, since nothing about a
#: truncated-but-still-parseable list looks wrong at a glance.
PARTITION_PROMPT = (
    'Given the question "{question}", which of the following keywords would '
    'be answered "Yes" to that question: {remaining}? (NO REASONING OR EXPLANATION)\n\n'
    "At the very end of your output, list only the YES keywords, comma-separated, as:\n"
    "**Yes**: keyword1, keyword2, ...\n"
    'If none of the keywords would be answered "Yes", write **Yes**: none.'
)


@dataclass
class TwentyQuestionsSession:
    """One played session's full state: the candidate universe plus the
    ``(question, remaining_after)`` pair recorded each turn.

    Deciding *which* branch (the partition's yes-set or no-set) actually
    becomes ``remaining_after`` is a game-play decision outside this
    dataclass's job — it only records whatever the caller already decided
    (see `notebooks_benzon/phase_0_calibration/5_twenty_questions.ipynb` for the notebook's
    own choice: a fixed secret keyword picked once per session, so each
    turn's real answer is determined by whether that keyword survived into
    the yes-set or the no-set).
    """

    keywords: tuple[str, ...]
    turns: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    def remaining_before(self, i: int) -> tuple[str, ...]:
        return self.keywords if i == 0 else self.turns[i - 1][1]

    @property
    def n_turns(self) -> int:
        return len(self.turns)

    def record_turn(self, question: str, remaining_after: tuple[str, ...]) -> None:
        self.turns.append((question, remaining_after))


def format_keywords(keywords: tuple[str, ...]) -> str:
    return ", ".join(keywords)


def build_next_question_prompt(session: TwentyQuestionsSession, turn_index: int) -> str:
    """`NEXT_QUESTION_PROMPT` filled in for turn ``turn_index`` (0-indexed) of ``session``."""
    remaining = session.remaining_before(turn_index)
    return NEXT_QUESTION_PROMPT.format(
        keywords=format_keywords(session.keywords), remaining=format_keywords(remaining)
    )


def build_partition_prompt(question: str, remaining: tuple[str, ...]) -> str:
    """`PARTITION_PROMPT` filled in for one just-generated ``question`` over ``remaining``."""
    return PARTITION_PROMPT.format(question=question, remaining=format_keywords(remaining))


def parse_partition(
    generation: str, remaining: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Parse the batched partition call's ``**Yes**: a, b, c`` (or ``none``)
    line into ``(yes_set, no_set)``.

    Every keyword in ``remaining`` not named after the ``**Yes**:`` marker is
    assumed NO — unlike a free-text answer key (`ground_truth.detect_yes_no_polarity`),
    there's no "unsure" bucket to make room for here, since ``remaining`` is
    the known, closed universe for this turn; a keyword the model's list
    just doesn't mention is exactly a "No" by construction of the prompt
    ("list only the YES keywords").
    """
    marker = "**Yes**:"
    idx = generation.find(marker)
    tail = generation[idx + len(marker):] if idx != -1 else generation
    tail = tail.strip().split("\n")[0].strip()
    if tail.lower().startswith("none"):
        yes_words: set[str] = set()
    else:
        yes_words = {w.strip().strip(".\"'").lower() for w in tail.split(",") if w.strip()}
    yes = tuple(k for k in remaining if k.lower() in yes_words)
    no = tuple(k for k in remaining if k.lower() not in yes_words)
    return yes, no
