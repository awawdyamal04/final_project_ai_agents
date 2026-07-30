"""Movement and barrier legality.

Pure validation: every function here either returns a verdict or raises, and
none of them changes anything. Application lives in
:mod:`police_thief.domain.transition`. Keeping the two apart is what makes
"an illegal action never partially modifies state" true by construction rather
than by careful coding.

All numeric bounds come from :class:`SharedConfig`.
"""

from __future__ import annotations

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ORTHOGONAL_DIRECTIONS, Direction, Role
from police_thief.domain.exceptions import (
    BarrierQuotaExceededError,
    BlockedCellError,
    IllegalMoveError,
    InvalidBarrierPlacementError,
    OutOfBoundsMoveError,
    UnauthorizedBarrierActionError,
)
from police_thief.domain.state import LocalState


# ----------------------------------------------------------------------
# Movement
# ----------------------------------------------------------------------


def is_move_allowed(direction: Direction, config: SharedConfig) -> bool:
    """Is ``direction`` in the agreed move set?

    ``move_set`` is FIXED at ``["N", "S", "E", "W", "STAY"]``, so in practice
    this always passes -- but reading it from configuration rather than assuming
    it is what keeps the rule where the specification put it.
    """
    return direction.value in config.movement_and_barriers.move_set


def destination_of(state: LocalState, direction: Direction) -> Coordinate:
    return state.position.shifted(direction)


def validate_move(
    state: LocalState, direction: Direction, config: SharedConfig
) -> Coordinate:
    """Check a move and return its destination. Raises on any violation.

    Order matters for the error type a caller sees: move-set membership, then
    bounds, then barriers -- from the most general rule to the most specific.
    """
    if not is_move_allowed(direction, config):
        raise IllegalMoveError(
            f"{direction.value} is not in the agreed move set "
            f"{list(config.movement_and_barriers.move_set)}"
        )

    destination = destination_of(state, direction)

    if not state.board.contains(destination):
        raise OutOfBoundsMoveError(
            f"moving {direction.value} from {state.position} leaves the "
            f"{state.board.size}x{state.board.size} board"
        )

    if state.board.is_blocked(destination):
        raise BlockedCellError(
            f"{destination} holds a barrier; barriers are impassable to both "
            f"players until the end of the game"
        )

    return destination


def is_move_legal(
    state: LocalState, direction: Direction, config: SharedConfig
) -> bool:
    try:
        validate_move(state, direction, config)
    except IllegalMoveError:
        return False
    return True


def legal_moves(state: LocalState, config: SharedConfig) -> tuple[Move, ...]:
    """Every legal move, in a deterministic order.

    Order is ``STAY`` first, then N, S, E, W -- fixed so that two peers
    enumerate identically and a test can assert on the sequence. Determinism
    here is not cosmetic: a strategy that iterates legal moves must produce the
    same choice on both sides of a replay.

    ``STAY`` is included when the configuration permits it, which it always
    does (``move_set`` is FIXED and contains it). It is filtered through the
    same validation as any other direction, so a cop standing on a cell it has
    barriered would correctly find ``STAY`` illegal.
    """
    ordered = (Direction.STAY, *ORTHOGONAL_DIRECTIONS)
    return tuple(
        Move(direction)
        for direction in ordered
        if is_move_legal(state, direction, config)
    )


def legal_relocations(
    state: LocalState, config: SharedConfig
) -> tuple[Move, ...]:
    """Legal moves that actually change cell -- i.e. excluding ``STAY``.

    This is the set E-47 is about. The rule says a thief "imprisoned with no
    legal move" is captured, and its parenthetical defines that precisely: *all
    adjacent cells blocked by barriers and/or board edges* (PDF p. 37). So
    standing still does not rescue a walled-in thief, and the trapped test must
    ask about relocations, not about moves in general.
    """
    return tuple(
        move for move in legal_moves(state, config) if move.direction.is_relocation
    )


def is_trapped(state: LocalState, config: SharedConfig) -> bool:
    """True when no relocation is available (E-47)."""
    return not legal_relocations(state, config)


# ----------------------------------------------------------------------
# Barriers
# ----------------------------------------------------------------------


def validate_barrier_placement(
    state: LocalState, cell: Coordinate, config: SharedConfig
) -> None:
    """Check a barrier placement. Raises on any violation.

    PDF p. 37: on a turn where the cop forgoes movement it may place a barrier
    on "any cell within one step of it -- the cell it stands on itself, or one
    of the four orthogonally adjacent cells".

    Note that the cop's own cell is an explicitly permitted target. That is the
    PDF's wording, and it raises a question it does not answer -- see
    OPEN_QUESTIONS.md Q-15.
    """
    if not state.may_place_barriers:
        raise UnauthorizedBarrierActionError(
            f"{state.role.value} may not place barriers; the barrier action "
            f"belongs to the cop alone"
        )

    remaining = state.barriers_remaining(config)
    if remaining <= 0:
        raise BarrierQuotaExceededError(
            f"barrier quota exhausted: "
            f"{config.movement_and_barriers.max_barriers} already placed"
        )

    if not state.board.contains(cell):
        raise InvalidBarrierPlacementError(
            f"{cell} is outside the {state.board.size}x{state.board.size} board"
        )

    if state.board.is_blocked(cell):
        raise InvalidBarrierPlacementError(
            f"{cell} already holds a barrier; barriers are irreversible and "
            f"cannot be stacked"
        )

    distance = state.position.manhattan_distance_to(cell)
    if distance > 1:
        raise InvalidBarrierPlacementError(
            f"{cell} is {distance} steps from the cop at {state.position}; a "
            f"barrier may only be placed on the cop's own cell or an "
            f"orthogonally adjacent one"
        )


def is_barrier_placement_legal(
    state: LocalState, cell: Coordinate, config: SharedConfig
) -> bool:
    try:
        validate_barrier_placement(state, cell, config)
    except (
        UnauthorizedBarrierActionError,
        BarrierQuotaExceededError,
        InvalidBarrierPlacementError,
    ):
        return False
    return True


def legal_barrier_placements(
    state: LocalState, config: SharedConfig
) -> tuple[PlaceBarrier, ...]:
    """Every legal placement, in the board's deterministic target order."""
    if not state.may_place_barriers or state.barriers_remaining(config) <= 0:
        return ()
    return tuple(
        PlaceBarrier(cell)
        for cell in state.board.placement_targets(state.position)
        if is_barrier_placement_legal(state, cell, config)
    )


# ----------------------------------------------------------------------
# Combined
# ----------------------------------------------------------------------


def legal_actions(state: LocalState, config: SharedConfig) -> tuple[Action, ...]:
    """All legal actions, moves before barrier placements, deterministically.

    For the thief this is just the legal moves; only the cop has the second
    kind of action.
    """
    return (*legal_moves(state, config), *legal_barrier_placements(state, config))


def validate_action(
    state: LocalState, action: Action, config: SharedConfig
) -> None:
    """Validate any action without applying it."""
    if isinstance(action, Move):
        validate_move(state, action.direction, config)
    elif isinstance(action, PlaceBarrier):
        validate_barrier_placement(state, action.cell, config)
    else:  # pragma: no cover - the union is closed
        raise IllegalMoveError(f"unknown action type: {type(action).__name__}")
