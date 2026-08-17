"""Barrier mechanics (PDF p. 37, E-15, E-16, E-46)."""

from __future__ import annotations

import pytest

from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ActionKind, Direction
from police_thief.domain.exceptions import (
    BarrierQuotaExceededError,
    BlockedCellError,
    InvalidBarrierPlacementError,
    UnauthorizedBarrierActionError,
)
from police_thief.domain.rules import (
    is_barrier_placement_legal,
    legal_barrier_placements,
    validate_barrier_placement,
)
from police_thief.domain.transition import apply_action, observe_barrier
from tests.domain.conftest import place_at, wall_in

# ----------------------------------------------------------------------
# Authorisation
# ----------------------------------------------------------------------


def test_cop_may_place_a_barrier(cop_state, shared_config):
    assert cop_state.may_place_barriers
    validate_barrier_placement(cop_state, Coordinate(0, 1), shared_config)


def test_thief_may_not_place_a_barrier(thief_state, shared_config):
    assert not thief_state.may_place_barriers
    with pytest.raises(UnauthorizedBarrierActionError, match="belongs to the cop"):
        validate_barrier_placement(thief_state, Coordinate(3, 4), shared_config)


def test_thief_barrier_action_is_rejected_by_the_transition(
    thief_state, shared_config
):
    with pytest.raises(UnauthorizedBarrierActionError):
        apply_action(thief_state, PlaceBarrier(Coordinate(3, 4)), shared_config)


def test_thief_has_no_legal_barrier_placements(thief_state, shared_config):
    assert legal_barrier_placements(thief_state, shared_config) == ()


# ----------------------------------------------------------------------
# Proximity
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "cell",
    [
        Coordinate(3, 3),  # own cell -- explicitly permitted by PDF p. 37
        Coordinate(2, 3),
        Coordinate(4, 3),
        Coordinate(3, 4),
        Coordinate(3, 2),
    ],
)
def test_placement_within_one_step_is_legal(cop_state, shared_config, cell):
    centred = place_at(cop_state, 3, 3)
    validate_barrier_placement(centred, cell, shared_config)


@pytest.mark.parametrize(
    "cell",
    [
        Coordinate(1, 3),  # two steps N
        Coordinate(3, 5),  # two steps E
        Coordinate(2, 2),  # diagonal
        Coordinate(4, 4),  # diagonal
        Coordinate(0, 0),  # far away
    ],
)
def test_placement_beyond_one_step_is_rejected(cop_state, shared_config, cell):
    centred = place_at(cop_state, 3, 3)
    with pytest.raises(InvalidBarrierPlacementError, match="steps from the cop"):
        validate_barrier_placement(centred, cell, shared_config)


def test_placement_outside_the_board_is_rejected(cop_state, shared_config):
    with pytest.raises(InvalidBarrierPlacementError, match="outside"):
        validate_barrier_placement(cop_state, Coordinate(-1, 0), shared_config)


def test_placement_on_an_existing_barrier_is_rejected(cop_state, shared_config):
    walled = wall_in(place_at(cop_state, 3, 3), [(3, 4)])
    with pytest.raises(InvalidBarrierPlacementError, match="already holds"):
        validate_barrier_placement(walled, Coordinate(3, 4), shared_config)


def test_legal_placements_are_deterministic_and_within_reach(
    cop_state, shared_config
):
    centred = place_at(cop_state, 3, 3)
    placements = legal_barrier_placements(centred, shared_config)
    assert [p.cell for p in placements] == [
        Coordinate(3, 3),
        Coordinate(2, 3),
        Coordinate(4, 3),
        Coordinate(3, 4),
        Coordinate(3, 2),
    ]
    for placement in placements:
        assert is_barrier_placement_legal(centred, placement.cell, shared_config)


def test_legal_placements_are_clipped_at_the_board_edge(cop_state, shared_config):
    """From the corner [0,0] only own cell, S and E are reachable."""
    assert [p.cell for p in legal_barrier_placements(cop_state, shared_config)] == [
        Coordinate(0, 0),
        Coordinate(1, 0),
        Coordinate(0, 1),
    ]


# ----------------------------------------------------------------------
# Quota
# ----------------------------------------------------------------------


def test_quota_comes_from_configuration(cop_state, shared_config):
    assert cop_state.barriers_remaining(shared_config) == (
        shared_config.movement_and_barriers.max_barriers
    )


def test_quota_is_enforced(cop_state, shared_config):
    quota = shared_config.movement_and_barriers.max_barriers
    exhausted = cop_state.__class__(
        role=cop_state.role,
        position=cop_state.position,
        board=cop_state.board,
        barriers_placed=quota,
    )
    assert exhausted.barriers_remaining(shared_config) == 0
    with pytest.raises(BarrierQuotaExceededError, match="quota exhausted"):
        validate_barrier_placement(exhausted, Coordinate(0, 1), shared_config)
    assert legal_barrier_placements(exhausted, shared_config) == ()


def test_placement_decrements_the_remaining_quota(cop_state, shared_config):
    quota = shared_config.movement_and_barriers.max_barriers
    result = apply_action(cop_state, PlaceBarrier(Coordinate(0, 1)), shared_config)
    assert result.state.barriers_placed == 1
    assert result.state.barriers_remaining(shared_config) == quota - 1


# ----------------------------------------------------------------------
# Placement replaces movement, and is permanent
# ----------------------------------------------------------------------


def test_placement_replaces_movement(cop_state, shared_config):
    """PDF p. 37: placement happens on a turn where the cop forgoes movement."""
    result = apply_action(cop_state, PlaceBarrier(Coordinate(0, 1)), shared_config)
    assert result.state.position == cop_state.position


def test_barrier_action_is_a_distinct_action_kind():
    """Not a flag on a move -- the rule makes them alternatives."""
    assert PlaceBarrier(Coordinate(0, 1)).kind is ActionKind.PLACE_BARRIER
    assert Move(Direction.N).kind is ActionKind.MOVE


def test_barrier_is_permanent(cop_state, shared_config):
    """Irreversible: a blocked cell stays blocked (PDF p. 37)."""
    state = apply_action(
        cop_state, PlaceBarrier(Coordinate(0, 1)), shared_config
    ).state
    for _ in range(3):
        state = apply_action(state, Move(Direction.S), shared_config).state
        assert state.board.is_blocked(Coordinate(0, 1))
    assert not hasattr(state.board, "remove_barrier")
    assert not hasattr(state.board, "clear_barriers")


def test_barrier_blocks_the_placing_cop(cop_state, shared_config):
    """It blocks both players -- including the one who placed it."""
    state = apply_action(
        cop_state, PlaceBarrier(Coordinate(0, 1)), shared_config
    ).state
    with pytest.raises(BlockedCellError):
        apply_action(state, Move(Direction.E), shared_config)


def test_barrier_blocks_the_thief(thief_state, cop_state, shared_config):
    """The thief records the cop's declared placement and is bound by it."""
    cop_result = apply_action(
        place_at(cop_state, 2, 3), PlaceBarrier(Coordinate(2, 3)), shared_config
    )
    thief_after = observe_barrier(thief_state, cop_result.barrier_cell)
    with pytest.raises(BlockedCellError):
        apply_action(thief_after, Move(Direction.N), shared_config)


def test_observing_a_barrier_does_not_consume_the_observer_quota(
    thief_state, shared_config
):
    """The counter tracks this peer's own quota; the thief has none."""
    after = observe_barrier(thief_state, Coordinate(2, 3))
    assert after.barriers_placed == 0
    assert after.board.is_blocked(Coordinate(2, 3))


def test_placement_emits_a_public_declaration_event(cop_state, shared_config):
    """E-15: every placement is openly declared with its exact location."""
    result = apply_action(cop_state, PlaceBarrier(Coordinate(0, 1)), shared_config)
    (event,) = result.events
    assert event.to_dict()["event"] == "barrier_placed"
    assert event.to_dict()["cell"] == [0, 1]
    assert result.barrier_cell == Coordinate(0, 1)


def test_illegal_placement_leaves_state_untouched(cop_state, shared_config):
    """Validation precedes application, so nothing is half-applied."""
    before = cop_state
    with pytest.raises(InvalidBarrierPlacementError):
        apply_action(cop_state, PlaceBarrier(Coordinate(5, 5)), shared_config)
    assert cop_state == before
    assert cop_state.board.barriers == frozenset()
    assert cop_state.barriers_placed == 0
