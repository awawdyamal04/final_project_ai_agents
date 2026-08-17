"""Minimal deterministic strategies for both roles.

Pure heuristics -- no learning, no language model, no search beyond one step.
The specification lists heuristics with a Bayesian belief map as one of the
equal-standing routes and the reference implementation's own default, so this is
a legitimate policy rather than a placeholder.

Both strategies score every legal action and take the best, breaking ties by a
fixed action ordering so the result is deterministic. Every candidate comes from
:func:`legal_actions`, so an illegal action is never even scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction
from police_thief.domain.rules import legal_actions, legal_moves
from police_thief.strategy.base import BaseStrategy, LocalView

LOOP_PENALTY = 2.5
"""Cost per recent visit to a candidate cell. Large enough to break a two-cell
oscillation, small enough that a genuinely good cell is still worth revisiting."""


def _destination(view: LocalView, action: Action) -> Coordinate:
    """Where this action leaves us. Barrier placement forgoes movement."""
    if isinstance(action, Move):
        return view.position.shifted(action.direction)
    return view.position


def _belief_peak(view: LocalView) -> Coordinate | None:
    return view.belief.peak()


@dataclass
class CopStrategy:
    """Pursue the belief peak, corroborated by scent; wall the thief in.

    Scoring, per candidate:

    * closer to the most-likely opponent cell is better -- the Manhattan metric
      is admissible on an orthogonal grid, so it never overestimates;
    * cells carrying the opponent's scent are better, since the trail is the one
      piece of evidence that cannot be faked;
    * recently-visited cells are penalised, which is what stops the cop
      oscillating between two squares when evidence is flat;
    * when belief is diffuse, the same distance term degenerates into a
      systematic sweep toward the centre of mass rather than a random walk.

    A barrier is placed only when it clearly helps: adjacent to the believed
    cell, and only once the belief is concentrated enough to be worth spending a
    quota unit on.
    """

    name: str = "cop-heuristic-v1"
    barrier_confidence: float = 0.15
    """Minimum belief mass near the target before a barrier is worth a quota unit."""

    crowd_threshold: int = 3
    """Close an escape route only once the quarry is down to this many exits.

    Pursuit alone cannot win: on an open grid both sides move one cell per turn,
    so a fleeing thief is never caught. Barriers are the cop's only way to
    change that, and they are worth spending once the thief is against an edge
    or corner where each one removes a real option.
    """

    def choose(self, view: LocalView) -> Action:
        candidates = legal_actions(view.state, view.config)
        if not candidates:
            return Move(Direction.STAY)

        target = _belief_peak(view)
        return max(candidates, key=lambda a: self._score(view, a, target))

    def _score(
        self, view: LocalView, action: Action, target: Coordinate | None
    ) -> tuple[float, ...]:
        cell = _destination(view, action)
        score = 0.0

        if isinstance(action, PlaceBarrier):
            return (self._barrier_score(view, action.cell, target),)

        if target is not None:
            score -= float(cell.manhattan_distance_to(target))
        score += 3.0 * view.opponent_scent.intensity_at(cell)
        score += 10.0 * view.belief.probability_at(cell)
        score -= LOOP_PENALTY * view.visits(cell)

        # Standing still is rarely right for a pursuer; nudge against it so a
        # tie resolves into movement rather than stagnation.
        if isinstance(action, Move) and action.direction is Direction.STAY:
            score -= 0.5

        return (score,)

    def _barrier_score(
        self, view: LocalView, cell: Coordinate, target: Coordinate | None
    ) -> float:
        """Worth spending a quota unit only to close a real escape route.

        Three conditions, all necessary. The cell must be adjacent to where we
        believe the thief is, so the barrier removes one of *its* options rather
        than decorating the board. The thief must already be short of exits, so
        the removal bites. And we must not be barriering our own cell, which
        would wall the pursuer in.
        """
        if target is None or cell == view.position:
            return -1e9
        if view.belief.probability_at(target) < self.barrier_confidence:
            return -1e9

        escapes = view.state.board.passable_neighbours(target)
        if not escapes or len(escapes) > self.crowd_threshold:
            return -1e9
        if cell not in escapes:
            return -1e9

        # Both sides move at once, so blocking the cell the quarry is *sitting*
        # on is useless -- it will have left. Block where it is going. The thief
        # flees to whichever exit is furthest from us, so that is the cell worth
        # closing, and closing the last one traps it outright.
        flight = max(
            escapes,
            key=lambda c: (c.manhattan_distance_to(view.position), -c.row, -c.col),
        )
        if cell != flight:
            return -1e9

        return 100.0 + (self.crowd_threshold - len(escapes))


@dataclass
class ThiefStrategy:
    """Maximise distance from where the cop is believed to be, and stay free.

    Scoring, per candidate:

    * further from the believed cop cell is better;
    * cells with more onward exits are better -- a corner is a trap even when it
      is momentarily distant, and the specification's own capture rule makes a
      thief with no legal relocation captured outright;
    * recently-visited cells are penalised, both to avoid loops and because
      lingering re-emits scent in the same place, which is a gift to the pursuer;
    * standing still is mildly discouraged for the same reason.
    """

    name: str = "thief-heuristic-v1"

    def choose(self, view: LocalView) -> Action:
        candidates = legal_moves(view.state, view.config)
        if not candidates:
            return Move(Direction.STAY)

        threat = _belief_peak(view)
        return max(candidates, key=lambda a: self._score(view, a, threat))

    def _score(
        self, view: LocalView, action: Move, threat: Coordinate | None
    ) -> tuple[float, ...]:
        cell = _destination(view, action)
        score = 0.0

        if threat is not None:
            score += 2.0 * float(cell.manhattan_distance_to(threat))

        # Freedom of movement. Being boxed in loses the game outright, so this
        # is survival, not comfort.
        exits = len(view.state.board.passable_neighbours(cell))
        score += 1.5 * exits

        score -= LOOP_PENALTY * view.visits(cell)
        score -= 4.0 * view.opponent_scent.intensity_at(cell)

        if action.direction is Direction.STAY:
            score -= 1.0

        return (score,)


def strategy_for(role_value: str) -> CopStrategy | ThiefStrategy:
    """The shipped default policy for a role."""
    return CopStrategy() if role_value == "police" else ThiefStrategy()


class StrategyLoadError(RuntimeError):
    """A configured ``[strategy]`` class path could not be loaded or is invalid."""


def load_strategy(role_value: str, class_path: str | None) -> BaseStrategy:
    """The strategy to run for this role: a configured override, or the default.

    ``class_path`` is the private config's ``[strategy] police_class`` /
    ``thief_class`` value (``config/*.toml.example``), in
    ``"module.path:ClassName"`` form -- a team's own brain, swapped in without
    touching the orchestrator. Empty or unset means the shipped heuristic
    (D-14).

    Fails loudly rather than falling back silently. A team that configured a
    custom brain and silently got the shipped default instead would not find
    out until it lost with the wrong strategy on the board; that is exactly
    the class of bug the config-hash mismatch check (E-11) exists to catch one
    layer up, so an override that cannot be loaded is a startup failure here
    too, not a quiet substitution.
    """
    if not class_path:
        return strategy_for(role_value)

    module_name, _, class_name = class_path.partition(":")
    if not module_name or not class_name:
        raise StrategyLoadError(
            f"strategy class path {class_path!r} must be 'module.path:ClassName'"
        )
    try:
        module = import_module(module_name)
    except ImportError as exc:
        raise StrategyLoadError(
            f"cannot import module {module_name!r} for strategy {class_path!r}: {exc}"
        ) from exc
    try:
        brain_class = getattr(module, class_name)
    except AttributeError as exc:
        raise StrategyLoadError(
            f"module {module_name!r} has no class {class_name!r}"
        ) from exc

    brain = brain_class()
    if not callable(getattr(brain, "choose", None)) or not hasattr(brain, "name"):
        raise StrategyLoadError(
            f"{class_path!r} does not implement the BaseStrategy protocol "
            "(needs .choose(view) and .name)"
        )
    return brain
