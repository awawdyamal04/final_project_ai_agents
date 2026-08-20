"""Seeded near-tie selection: pick among near-best candidates reproducibly.

The anti-predictability requirement of the strategy sprint, factored out so
both new strategies share one implementation. A single seed makes an
otherwise-random tie-break replayable -- the same seed and the same sequence
of near-ties always yields the same action, so a match run with a supplied
seed reproduces exactly.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def pick_near_best(  # noqa: UP047 - TypeVar kept for consistency with peer/deadline.py
    candidates: Sequence[T],
    score: Callable[[T], float],
    epsilon: float,
    rng: random.Random,
) -> T:
    """Score every candidate, then choose uniformly among those within
    ``epsilon`` of the best score, using ``rng``.

    Candidates are sorted into a fixed order first (by their own string form)
    so the *set* offered to the RNG is deterministic before randomness is
    applied -- the RNG breaks ties, it does not also decide the field.
    """
    scored = [(candidate, score(candidate)) for candidate in candidates]
    best = max(value for _, value in scored)
    near_best = sorted(
        (candidate for candidate, value in scored if value >= best - epsilon),
        key=str,
    )
    return rng.choice(near_best)
