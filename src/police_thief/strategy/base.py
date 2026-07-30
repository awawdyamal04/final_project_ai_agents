"""Strategy interface and the local view a strategy is allowed to see.

The separation the specification insists on: a strategy decides *what to do*,
and it does so from the peer's own legal information only. It has no access to
the opponent's true position, to a harness, or to any global state -- the type
it receives cannot express them.

Deterministic by contract. Given the same :class:`LocalView` a strategy returns
the same action, so a replay reproduces the game and two peers reasoning about
the same evidence agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import Action
from police_thief.domain.belief import BeliefMap
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.scent import ScentField
from police_thief.domain.state import LocalState


@dataclass(frozen=True, slots=True)
class LocalView:
    """Everything a strategy may legally know.

    Note what is absent, and cannot be added without changing this class: the
    opponent's position, the opponent's state, any adjudicator, any harness.
    A strategy that wanted to cheat would have nowhere to read it from.
    """

    state: LocalState
    """This peer's own truth: its cell, the public barriers, the turn."""

    config: SharedConfig
    belief: BeliefMap
    """Where the opponent probably is -- a distribution, never a fact."""

    opponent_scent: ScentField
    """The opponent's trail. Each side reads the other's field, not its own."""

    recent_cells: tuple[Coordinate, ...] = ()
    """This peer's own recent positions, for loop avoidance."""

    @property
    def position(self) -> Coordinate:
        return self.state.position

    def visits(self, cell: Coordinate) -> int:
        return self.recent_cells.count(cell)


class BaseStrategy(Protocol):
    """Chooses one legal action per turn."""

    name: str

    def choose(self, view: LocalView) -> Action: ...


def score_of(candidate: tuple[float, ...]) -> tuple[float, ...]:
    """Identity helper, kept so scoring tuples read the same everywhere."""
    return candidate
