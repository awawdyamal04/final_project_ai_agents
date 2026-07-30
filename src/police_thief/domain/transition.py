"""The transition function: apply one action to one peer's local state.

Deterministic. The same ``(state, action, config)`` always produces the same
result, which is what lets the replay verifier re-derive a whole match from a
move list plus the config, and what makes a hash mismatch mean tampering rather
than nondeterminism.

Four stages, deliberately separate:

1. **Validation** -- :mod:`police_thief.domain.rules`. Raises before anything
   changes.
2. **Application** -- here. Builds a new state; never mutates the old one.
3. **Terminal evaluation** -- :mod:`police_thief.domain.terminal` and
   :mod:`police_thief.domain.capture`, driven by the adjudicator.
4. **Scoring** -- :mod:`police_thief.domain.scoring`.

Scope: this function is **local**. It applies *this* peer's action to *this*
peer's state. It has no opponent parameter and cannot detect a capture that
depends on both positions -- that is the adjudicator's job
(:mod:`police_thief.sim.harness`), and in the real game the capture-claim
protocol's. The one exception is E-46: a barrier placement can capture, and the
adjudicator is told so through :attr:`TransitionResult.barrier_cell` rather than
by this function reaching for the thief's position.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Role
from police_thief.domain.events import AgentMoved, BarrierPlaced, DomainEvent
from police_thief.domain.exceptions import (
    GameAlreadyFinishedError,
    InvalidTransitionError,
)
from police_thief.domain.rules import validate_action
from police_thief.domain.state import LocalState
from police_thief.domain.terminal import TerminalResult


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """The outcome of applying one action.

    ``terminal`` is populated only for conditions this peer can establish
    alone. Capture is not one of them, except via ``barrier_cell``.
    """

    state: LocalState
    events: tuple[DomainEvent, ...] = field(default_factory=tuple)
    terminal: TerminalResult | None = None
    barrier_cell: Coordinate | None = None
    """Set when the action placed a barrier.

    The adjudicator compares it against the thief's position to apply E-46. The
    transition function does not do that comparison itself, because it would
    need the thief's position to do so.
    """

    @property
    def moved_to(self) -> Coordinate:
        return self.state.position


def apply_action(
    state: LocalState, action: Action, config: SharedConfig
) -> TransitionResult:
    """Validate and apply ``action``, returning a new state.

    Raises before any change if the action is illegal, so a rejected action
    leaves the caller's state byte-identical to what it was. The old state
    object is never mutated -- it is frozen.
    """
    if state.is_finished:
        raise GameAlreadyFinishedError(
            f"the sub-game ended at turn {state.terminal.turn} "
            f"({state.terminal.reason.value}); no further action is possible"
        )

    # Stage 1: validation. Raises without touching anything.
    validate_action(state, action, config)

    # Stage 2: application.
    if isinstance(action, Move):
        return _apply_move(state, action, config)
    if isinstance(action, PlaceBarrier):
        return _apply_barrier(state, action, config)

    raise InvalidTransitionError(  # pragma: no cover - the union is closed
        f"unknown action type: {type(action).__name__}"
    )


def _apply_move(
    state: LocalState, action: Move, config: SharedConfig
) -> TransitionResult:
    origin = state.position
    destination = origin.shifted(action.direction)
    new_state = state.with_position(destination)

    event = AgentMoved(
        role=state.role,
        direction=action.direction,
        origin=origin,
        destination=destination,
        turn=state.turn,
    )
    return TransitionResult(state=new_state, events=(event,))


def _apply_barrier(
    state: LocalState, action: PlaceBarrier, config: SharedConfig
) -> TransitionResult:
    """Place a barrier. The cop forgoes movement, so its position is unchanged.

    PDF p. 37: placement is an alternative *to* moving, not an addition to it.
    """
    new_board = state.board.with_barrier(action.cell)
    placed = state.barriers_placed + 1
    new_state = replace(state, board=new_board, barriers_placed=placed)

    event = BarrierPlaced(
        role=state.role,
        cell=action.cell,
        turn=state.turn,
        barriers_placed=placed,
        barriers_remaining=new_state.barriers_remaining(config),
    )
    return TransitionResult(
        state=new_state, events=(event,), barrier_cell=action.cell
    )


def observe_barrier(state: LocalState, cell: Coordinate) -> LocalState:
    """Record a barrier the *opponent* declared.

    Barriers are public knowledge by obligation (E-15, E-16), so both peers must
    converge on an identical set or they are playing different games. The thief
    learns of a placement through the cop's declaration and records it here.

    This is not a leak: the declaration is mandatory and its content is exactly
    the cell, nothing more. It does not reveal where the cop *is* -- a barrier
    may sit on any of five cells around it.

    ``barriers_placed`` is not incremented: that counter tracks *this* peer's
    own quota consumption, and the thief has no quota.
    """
    return state.with_board(state.board.with_barrier(cell))
