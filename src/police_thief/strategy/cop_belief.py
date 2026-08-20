"""Belief-state cop strategy with shallow lookahead (competitive strategy
sprint).

Same legal-information contract as the shipped heuristic
(:mod:`police_thief.strategy.heuristics`): every score is a function of
``LocalView`` alone -- this peer's own state, its belief over the thief's
cell, the thief's reconstructed scent, and its own recent cells. No opponent
coordinate is read, directly or indirectly.

Unlike the one-ply baseline, each candidate is scored using a short BFS
lookahead against the top few believed cells (not only the single peak), a
graded barrier-trap evaluation, and a lightweight read on the opponent's own
movement/barrier tendencies (:mod:`police_thief.strategy.opponent_model`).
Near-equal candidates are broken by a seeded RNG (see
:mod:`police_thief.strategy.rng_utils`), so a match with a supplied seed
still reproduces exactly.

Activate with a private ``[strategy]`` override, e.g.::

    police_class = "police_thief.strategy.cop_belief:BeliefCopStrategy"
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction
from police_thief.domain.rules import legal_actions
from police_thief.strategy.base import LocalView
from police_thief.strategy.cop_lookahead import (
    barrier_trap_value,
    capture_soon_score,
)
from police_thief.strategy.opponent_model import OpponentModel
from police_thief.strategy.rng_utils import pick_near_best
from police_thief.strategy.weights import CopWeights


def _destination(view: LocalView, action: Action) -> Coordinate:
    if isinstance(action, Move):
        return view.position.shifted(action.direction)
    return view.position


@dataclass
class BeliefCopStrategy:
    """Pursue the belief distribution, not just its peak, with lookahead."""

    name: str = "cop-belief-v1"
    weights: CopWeights = field(default_factory=CopWeights)
    opponent_model: OpponentModel = field(default_factory=OpponentModel)
    seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose(self, view: LocalView) -> Action:
        self.opponent_model.observe(view)
        candidates = legal_actions(view.state, view.config)
        if not candidates:
            return Move(Direction.STAY)
        return pick_near_best(
            candidates,
            lambda action: self._score(view, action),
            self.weights.near_tie_epsilon,
            self._rng,
        )

    def _score(self, view: LocalView, action: Action) -> float:
        if isinstance(action, PlaceBarrier):
            return self._barrier_score(view, action.cell)

        w = self.weights
        cell = _destination(view, action)
        score = 0.0
        score += w.capture_now * view.belief.probability_at(cell)
        score += w.capture_soon * capture_soon_score(
            view.state.board, cell, view.belief, w.lookahead_top_k, w.lookahead_horizon
        )
        score += w.scent * view.opponent_scent.intensity_at(cell)
        score -= w.loop_penalty * view.visits(cell)

        peak = view.belief.peak()
        if peak is not None:
            dist_now = view.position.manhattan_distance_to(peak)
            dist_after = cell.manhattan_distance_to(peak)
            score -= w.belief * (dist_after / view.state.board.size)
            score += w.edge_push * self._edge_pressure(view, peak)
            if dist_after < dist_now:
                score += w.info_gain * (1.0 - view.belief.probability_at(peak))
            score += w.opponent_bias * self._interception_bonus(action)

        if isinstance(action, Move) and action.direction is Direction.STAY:
            score -= w.stay_penalty

        return score

    def _edge_pressure(self, view: LocalView, peak: Coordinate) -> float:
        """Reward positioning that squeezes the believed cell's exits."""
        exits = len(view.state.board.passable_neighbours(peak))
        return max(0.0, 4 - exits) / 4.0

    def _interception_bonus(self, action: Action) -> float:
        """Lean toward the direction the opponent model says the thief favours."""
        if not isinstance(action, Move) or action.direction is Direction.STAY:
            return 0.0
        return self.opponent_model.direction_bias(action.direction)

    def _barrier_score(self, view: LocalView, cell: Coordinate) -> float:
        w = self.weights
        peak = view.belief.peak()
        if peak is None or cell == view.position:
            return -1e9
        if view.belief.probability_at(peak) < w.barrier_confidence:
            return -1e9

        escapes = view.state.board.passable_neighbours(peak)
        if not escapes or len(escapes) > w.crowd_threshold:
            return -1e9
        if cell not in escapes:
            return -1e9

        # Both sides move at once, so the cell worth closing is where the
        # quarry is fleeing *to*, not where it currently stands.
        flight = max(
            escapes,
            key=lambda c: (c.manhattan_distance_to(view.position), -c.row, -c.col),
        )
        if cell != flight:
            return -1e9

        return w.barrier_trap_bonus + barrier_trap_value(view.state.board, peak)
