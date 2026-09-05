"""Shared tag-based subclass lookup for `vonto.ground_truth` and
`vonto.observation_method` — both packages expose the same ``ALL``/``get``
shape over their own base class's concrete subclasses, so the lookup itself
lives here once instead of twice."""

from __future__ import annotations


def all_subclasses(base: type) -> list[type]:
    """Every concrete descendant of ``base``, walked transitively — needed
    because e.g. `ObservationMethod`'s concrete subclasses (`ConfidenceOM`,
    ...) sit one level further down, under the abstract `LikertOM`. "Concrete"
    means the class sets its own ``tags`` (``base`` and an abstract
    intermediate like `LikertOM` only ever inherit the bare type annotation,
    never a real value), so those are skipped rather than treated as results.
    """

    found: list[type] = []

    def walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            if "tags" in vars(sub):
                found.append(sub)
            walk(sub)

    walk(base)
    return found


def get(subclasses: list[type]):
    """``get(subclasses)(tags, tags, ...)`` -> the matching subclasses.

    Each ``tags`` argument is its own AND-filter group — a subclass must
    carry *every* tag in that group to survive it — and the groups are then
    unioned (concatenated) together, so a class matching more than one group
    appears once per group it matches:

        get(ALL)([t1, t2]) == get(get(ALL)([t1]))([t2])          # AND within a group
        get(ALL)([t1], [t2]) == get(ALL)([t1]) + get(ALL)([t2])  # OR across groups
    """

    def _get(*tag_groups: list[str]) -> list[type]:
        result: list[type] = []
        for tags in tag_groups:
            group = subclasses
            for tag in tags:
                group = [cls for cls in group if tag in cls.tags]
            result += group
        return result

    return _get
