# SPDX-License-Identifier: AGPL-3.0-or-later
"""The two assistance axes and their three signals.

Writing and analysis are separate ordinal axes. Each has three signals (declared,
predicted, readers) that are stored and shown separately and never merged, averaged, or
weighted together (SPEC §4.5.1). Nothing in this module combines signals or axes.
"""

from __future__ import annotations

from dataclasses import dataclass

WRITING = {
    "W0": "Human wrote it",
    "W1": "Human wrote, model polished",
    "W2": "Model drafted, human edited",
    "W3": "Model wrote it, light or no human edits",
}
ANALYSIS = {
    "A0": "Human did the analysis",
    "A1": "Model assisted, checked by a human",
    "A2": "Model did the analysis",
}
AXES = {"writing": WRITING, "analysis": ANALYSIS}
AXIS_NAMES = {"writing": "Writing", "analysis": "Analysis"}
INTERVAL_MASS = 0.9
MIN_VOTES_FOR_MEDIAN = 5


def codes(axis: str) -> list[str]:
    return list(AXES[axis])


def gloss(code: str) -> str:
    for table in AXES.values():
        if code in table:
            return table[code]
    raise KeyError(code)


def axis_of(code: str) -> str:
    return "writing" if code.startswith("W") else "analysis"


@dataclass(frozen=True)
class Interval:
    point: str
    low: str
    high: str
    members: tuple[str, ...]
    mass: float


def predicted_interval(axis: str, probabilities: dict[str, float], mass: float = INTERVAL_MASS) -> Interval:
    """Most probable code and the smallest contiguous run of codes holding >= mass.

    Ties between equally short runs go to the one with more probability, then to the
    one that contains the point estimate (SPEC §4.5.5).
    """
    order = codes(axis)
    p = [float(probabilities.get(c, 0.0)) for c in order]
    total = sum(p) or 1.0
    p = [x / total for x in p]
    point = order[max(range(len(p)), key=lambda i: (p[i], -i))]
    best: tuple | None = None
    for width in range(1, len(order) + 1):
        for start in range(0, len(order) - width + 1):
            m = sum(p[start : start + width])
            if m + 1e-9 >= mass:
                contains = order.index(point) in range(start, start + width)
                cand = (width, -m, 0 if contains else 1, start)
                if best is None or cand < best:
                    best = cand
        if best is not None:
            break
    width, neg_m, _, start = best  # type: ignore[misc]
    members = tuple(order[start : start + width])
    return Interval(point, members[0], members[-1], members, -neg_m)


@dataclass(frozen=True)
class Median:
    """Community median on one axis (SPEC §4.5.9). When the two middle votes differ,
    both codes are kept, since no code lies between them."""

    low: str
    high: str
    votes: int

    def __str__(self) -> str:
        return self.low if self.low == self.high else f"{self.low} to {self.high}"


def median(axis: str, counts: dict[str, int], min_votes: int = MIN_VOTES_FOR_MEDIAN) -> Median | None:
    """Ordinal median on one axis, or None below `min_votes` votes."""
    order = codes(axis)
    n = sum(int(counts.get(c, 0)) for c in order)
    if n < min_votes or n == 0:
        return None

    def code_at(position: int) -> str:  # 1-indexed position in the sorted votes
        cum = 0
        for c in order:
            cum += int(counts.get(c, 0))
            if cum >= position:
                return c
        return order[-1]

    if n % 2:
        c = code_at((n + 1) // 2)
        return Median(c, c, n)
    return Median(code_at(n // 2), code_at(n // 2 + 1), n)
