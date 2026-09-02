"""Keyword sampling and 20-Questions game-play — the shared category/keyword
universe every procedurally generated `vonto.dataset` dataset draws from,
plus the game loop that actually plays a 20-Questions session.

Keywords are drawn from real English usage (Brown-corpus frequency),
restricted to a WordNet category, rather than a hand-picked list — no dataset
here is hardcoded.
"""

from __future__ import annotations

import functools

import numpy as np

#: Ten WordNet noun categories: 7 concrete (physical-referent), 3 abstract —
#: a concreteness split is available for a concrete-vs-abstract comparison,
#: not just an aggregate one.
CATEGORIES: tuple[str, ...] = (
    "animal.n.01", "plant.n.02", "food.n.01", "body_part.n.01", "vehicle.n.01",
    "structure.n.01", "container.n.01",
    "emotion.n.01", "cognition.n.01", "attribute.n.02",
)

#: The 3 categories in `CATEGORIES` with no physical referent.
ABSTRACT_CATEGORIES: tuple[str, ...] = ("emotion.n.01", "cognition.n.01", "attribute.n.02")


def _ensure_nltk_data() -> None:
    import nltk

    for resource, package in [
        ("corpora/brown", "brown"),
        ("corpora/wordnet", "wordnet"),
    ]:
        try:
            nltk.data.find(resource)
        except LookupError:
            nltk.download(package, quiet=True)


@functools.lru_cache(maxsize=1)
def _brown_noun_counts() -> dict[str, int]:
    """Common-noun (``NN``/``NNS``) token frequency counts from the Brown
    corpus, cached process-wide — re-scanning it on every sample call would be
    pure waste."""
    _ensure_nltk_data()
    from nltk.corpus import brown

    counts: dict[str, int] = {}
    for word, tag in brown.tagged_words():
        if tag in ("NN", "NNS") and word.isalpha() and len(word) >= 3:
            word = word.lower()
            counts[word] = counts.get(word, 0) + 1
    return counts


@functools.lru_cache(maxsize=None)
def _category_members(category: str) -> tuple[str, ...]:
    """Brown-corpus words that are (a sense of) ``category`` or one of its
    hyponyms, per WordNet — cached per category for the same reason
    `_brown_noun_counts` is cached whole."""
    _ensure_nltk_data()
    from nltk.corpus import wordnet as wn

    target = wn.synset(category)
    hyponym_closure = set(target.closure(lambda s: s.hyponyms())) | {target}
    return tuple(
        word
        for word in _brown_noun_counts()
        if any(s in hyponym_closure for s in wn.synsets(word, pos=wn.NOUN))
    )


@functools.lru_cache(maxsize=None)
def _category_closure(category: str) -> frozenset:
    """Every synset under ``category`` (itself included), per WordNet
    hyponymy — the membership test `classify_word` needs, split out from
    `_category_members` since that one also filters through the Brown corpus,
    which a freshly generated word won't generally appear in."""
    _ensure_nltk_data()
    from nltk.corpus import wordnet as wn

    target = wn.synset(category)
    return frozenset(target.closure(lambda s: s.hyponyms())) | {target}


def classify_word(word: str) -> str | None:
    """Which of `CATEGORIES` ``word`` belongs to (by WordNet hyponymy), or
    ``None`` if none of its noun senses fall under any of them — e.g. for
    grading how "on-topic" a generated list of items stays relative to its
    own seed category."""
    _ensure_nltk_data()
    from nltk.corpus import wordnet as wn

    synsets = set(wn.synsets(word.lower(), pos=wn.NOUN))
    if not synsets:
        return None
    for category in CATEGORIES:
        if synsets & _category_closure(category):
            return category
    return None


def sample_natural_keywords(n: int = 100, seed: int = 0, category: str | None = None) -> tuple[str, ...]:
    """``n`` unique English common nouns, weighted by natural occurrence
    frequency in written English (the Brown corpus) rather than a hand-picked
    list, optionally restricted to ``category`` (a WordNet noun synset name)
    and its hyponyms. ``seed`` makes the sample reproducible.
    """
    counts = _brown_noun_counts()
    words = list(_category_members(category)) if category is not None else list(counts)
    weights = np.array([counts[w] for w in words], dtype=float)
    weights /= weights.sum()
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(words), size=min(n, len(words)), replace=False, p=weights)
    return tuple(words[i] for i in chosen)


# --------------------------------------------------------------------------- #
# Game play
# --------------------------------------------------------------------------- #

GAME_RULES_TEMPLATE = (
    "You are playing 20 Questions. The secret word is one of the following "
    "{n} candidates:\n{keywords}\n\n"
    "Ask yes/no questions to narrow down the candidates. Try to split the "
    "remaining candidates as evenly as possible with each question, the way "
    "an optimal binary search would."
)

PARTITION_PROMPT = (
    "Question: {question}\n"
    "Candidates: {remaining}\n\n"
    'For each candidate, answer Yes or No to the question above. List every '
    'candidate for which the answer is Yes, comma-separated, after "**Yes**:" '
    '(write "**Yes**: none" if none apply).'
)


def format_keywords(keywords: tuple[str, ...]) -> str:
    return ", ".join(keywords)


def build_conversation_for_next_question(
    keywords: tuple[str, ...], qa_history: list[tuple[str, str]]
) -> list[dict[str, str]]:
    """Chat messages for generating the *next* question, ending right where the
    model's own next turn should begin — pass to
    ``tokenizer.apply_chat_template(messages, add_generation_prompt=True)``.
    """
    messages = [
        {
            "role": "user",
            "content": (
                GAME_RULES_TEMPLATE.format(n=len(keywords), keywords=format_keywords(keywords))
                + "\n\nAsk your first yes/no question."
            ),
        }
    ]
    for question, answer in qa_history:
        messages.append({"role": "assistant", "content": question})
        messages.append({"role": "user", "content": f"{answer}. Ask your next yes/no question."})
    return messages


def transcript_summary(keywords: tuple[str, ...], qa_history: list[tuple[str, str]]) -> str:
    """A plain-text restatement of exactly what the model actually had access
    to when it asked its most recent question."""
    lines = [GAME_RULES_TEMPLATE.format(n=len(keywords), keywords=format_keywords(keywords))]
    lines += [f"Q: {q}\nA: {a}" for q, a in qa_history]
    return "\n".join(lines)


def build_partition_prompt(question: str, remaining: tuple[str, ...]) -> str:
    """`PARTITION_PROMPT` filled in for one just-generated ``question`` over ``remaining``."""
    return PARTITION_PROMPT.format(question=question, remaining=format_keywords(remaining))


def parse_partition(
    generation: str, remaining: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Parse the batched partition call's ``**Yes**: a, b, c`` (or ``none``)
    line into ``(yes_set, no_set)`` — every candidate in ``remaining`` not
    named after the ``**Yes**:`` marker is assumed No.

    Only the rest of *that one line* is read as the candidate list, not
    everything after the marker to the end of the generation — a model that
    keeps talking past the list (e.g. explaining its reasoning afterward) has
    its own commas, and splitting on those too used to silently corrupt the
    intended list: ``"**Yes**: dog, cat\\n\\nI chose these because sheep,
    ..."`` would merge ``"cat"`` with ``"\\n\\nI chose these because sheep"``
    into one non-matching blob, silently dropping ``"cat"`` from the parsed
    yes-set even though the model clearly listed it.
    """
    idx = generation.find("**Yes**:")
    if idx == -1:
        yes_text = ""
    else:
        yes_text = generation[idx + len("**Yes**:") :].split("\n", 1)[0]
    yes_words = {w.strip().lower().rstrip(".,;") for w in yes_text.split(",")}
    yes_set = tuple(w for w in remaining if w.lower() in yes_words)
    no_set = tuple(w for w in remaining if w not in yes_set)
    return yes_set, no_set
