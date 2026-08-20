"""Lightweight opponent-tendency tracking, from legally observed evidence only
(competitive strategy sprint, "opponent modelling" section).

Everything here is derived from what a single call to ``choose(view)`` can
see: the public barrier set already on the board, and this peer's own belief
map. No opponent coordinate, no hidden state, no replay -- see
``LocalState``/``LocalView`` for why those are structurally unavailable to a
live peer, and never imported here either.

Barrier growth is exact evidence (barriers are public, E-15/E-16). Direction
tendency is inferred from how this peer's own *believed* cell drifts between
calls -- an honest proxy for the opponent's habits, built entirely from our
own uncertain estimate, not its true trajectory -- and it degrades to "no
opinion" when belief is diffuse or has not moved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ORTHOGONAL_DIRECTIONS, Direction
from police_thief.strategy.base import LocalView

_DECAY = 0.9
"""Old evidence matters less than new -- tendencies can shift mid-match."""


@dataclass
class OpponentModel:
    """One peer's running read on the other side's habits."""

    direction_counts: dict[Direction, float] = field(default_factory=dict)
    barrier_events: float = 0.0
    turns_observed: int = 0
    _last_barrier_count: int | None = field(default=None, init=False, repr=False)
    _last_peak: Coordinate | None = field(default=None, init=False, repr=False)

    def observe(self, view: LocalView) -> None:
        """Fold this turn's legal evidence in. Call once per ``choose()``."""
        self._observe_barriers(len(view.state.board.barriers))
        self._observe_belief_drift(view)
        self.turns_observed += 1

    def _observe_barriers(self, barrier_count: int) -> None:
        if self._last_barrier_count is not None:
            grown = barrier_count - self._last_barrier_count
            if grown > 0:
                self.barrier_events = self.barrier_events * _DECAY + grown
        self._last_barrier_count = barrier_count

    def _observe_belief_drift(self, view: LocalView) -> None:
        peak = view.belief.peak()
        if peak is not None and self._last_peak is not None and peak != self._last_peak:
            direction = view.state.board.direction_between(self._last_peak, peak)
            if direction is not None and direction is not Direction.STAY:
                for d in ORTHOGONAL_DIRECTIONS:
                    self.direction_counts[d] = self.direction_counts.get(d, 0.0) * _DECAY
                self.direction_counts[direction] = (
                    self.direction_counts.get(direction, 0.0) + 1.0
                )
        self._last_peak = peak

    def barrier_rate(self) -> float:
        """Roughly how often barriers have been showing up -- 0 with none yet."""
        if self.turns_observed == 0:
            return 0.0
        return min(1.0, self.barrier_events / max(1.0, self.turns_observed))

    def direction_bias(self, direction: Direction) -> float:
        """Normalised tendency toward ``direction``, in ``[0, 1]``."""
        total = sum(self.direction_counts.values())
        if total <= 0.0:
            return 0.0
        return self.direction_counts.get(direction, 0.0) / total
