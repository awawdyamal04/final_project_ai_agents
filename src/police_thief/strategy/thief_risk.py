"""Survival-risk thief strategy with escape-route awareness (competitive
strategy sprint).

Same legal-information contract as the baseline: every score is a function
of ``LocalView`` alone. ``opponent_scent`` here is the *cop's* trail -- each
side reads the other's field (see ``LocalView`` docstring) -- so steering
away from it is legal evasion, not mind-reading, exactly as in the shipped
:class:`police_thief.strategy.heuristics.ThiefStrategy`.

Near-equal candidates are broken by a seeded RNG rather than a fixed
tie-break, so the thief is not perfectly predictable across repeated
matches, while remaining exactly reproducible when a seed is supplied.

Activate with a private ``[strategy]`` override, e.g.::

    thief_class = "police_thief.strategy.thief_risk:RiskThiefStrategy"
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from police_thief.domain.actions import Move
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction
from police_thief.domain.rules import legal_moves
from police_thief.strategy.base import LocalView
from police_thief.strategy.opponent_model import OpponentModel
from police_thief.strategy.rng_utils import pick_near_best
from police_thief.strategy.weights import ThiefWeights

_OPPOSITE: dict[Direction, Direction] = {
    Direction.N: Direction.S,
    Direction.S: Direction.N,
    Direction.E: Direction.W,
    Direction.W: Direction.E,
}


@dataclass
class RiskThiefStrategy:
    """Maximise survival odds: mobility, distance, and confinement avoidance."""

    name: str = "thief-risk-v1"
    weights: ThiefWeights = field(default_factory=ThiefWeights)
    opponent_model: OpponentModel = field(default_factory=OpponentModel)
    seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose(self, view: LocalView) -> Move:
        self.opponent_model.observe(view)
        candidates = legal_moves(view.state, view.config)
        if not candidates:
            return Move(Direction.STAY)
        return pick_near_best(
            candidates,
            lambda action: self._score(view, action),
            self.weights.near_tie_epsilon,
            self._rng,
        )

    def _score(self, view: LocalView, action: Move) -> float:
        w = self.weights
        cell = view.position.shifted(action.direction)
        score = 0.0

        threat = view.belief.peak()
        if threat is not None:
            score += w.threat_distance * float(cell.manhattan_distance_to(threat))
            score += w.opponent_bias * self._flee_alignment(action)

        exits = view.state.board.passable_neighbours(cell)
        score += w.mobility * len(exits)
        score += w.future_mobility * self._future_mobility(view, cell)
        if len(exits) <= 1:
            # A near dead-end only stands if distance/mobility terms above
            # already outweigh this -- see ThiefWeights.corner_penalty.
            score -= w.corner_penalty

        score -= w.barrier_confinement * self._barrier_pressure(view, cell)
        score -= w.scent * view.opponent_scent.intensity_at(cell)
        score -= w.loop_penalty * view.visits(cell)
        if action.direction is Direction.STAY:
            score -= w.stay_penalty

        return score

    def _future_mobility(self, view: LocalView, cell: Coordinate) -> float:
        """Onward exits from every neighbour of ``cell`` -- room two turns out."""
        board = view.state.board
        return float(
            sum(len(board.passable_neighbours(n)) for n in board.passable_neighbours(cell))
        )

    def _barrier_pressure(self, view: LocalView, cell: Coordinate) -> float:
        """Barriers within two steps -- a confinement-risk proxy, weighted up
        when the opponent model shows a habit of barriering."""
        nearby = sum(
            1 for b in view.state.board.barriers if cell.manhattan_distance_to(b) <= 2
        )
        return nearby * (1.0 + self.opponent_model.barrier_rate())

    def _flee_alignment(self, action: Move) -> float:
        """Extra weight against the cop's most habitual approach direction."""
        favoured, bias = None, 0.0
        for direction in (Direction.N, Direction.S, Direction.E, Direction.W):
            candidate_bias = self.opponent_model.direction_bias(direction)
            if candidate_bias > bias:
                favoured, bias = direction, candidate_bias
        if favoured is None or bias <= 0.0:
            return 0.0
        return bias if action.direction == _OPPOSITE[favoured] else 0.0
