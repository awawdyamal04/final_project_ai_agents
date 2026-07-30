"""Movement legality and deterministic legal-action generation."""

from __future__ import annotations

import pytest

from police_thief.domain.actions import Move
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role
from police_thief.domain.exceptions import (
    BlockedCellError,
    IllegalMoveError,
    OutOfBoundsMoveError,
)
from police_thief.domain.rules import (
    is_move_legal,
    is_trapped,
    legal_actions,
    legal_moves,
    legal_relocations,
    validate_move,
)
from police_thief.domain.state import LocalState
from tests.domain.conftest import place_at, wall_in


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        (Direction.N, Coordinate(2, 3)),
        (Direction.S, Coordinate(4, 3)),
        (Direction.E, Coordinate(3, 4)),
        (Direction.W, Coordinate(3, 2)),
        (Direction.STAY, Coordinate(3, 3)),
    ],
)
def test_each_direction_is_legal_from_the_board_interior(
    thief_state, shared_config, direction, expected
):
    assert validate_move(thief_state, direction, shared_config) == expected


def test_stay_is_a_legal_action(thief_state, shared_config):
    """move_set is FIXED at four directions "+ standing" (Appendix F table 15)."""
    assert Direction.STAY.value in shared_config.movement_and_barriers.move_set
    assert is_move_legal(thief_state, Direction.STAY, shared_config)
    assert Move(Direction.STAY) in legal_moves(thief_state, shared_config)


def test_moving_off_the_north_edge_is_rejected(cop_state, shared_config):
    """The cop starts at [0,0]; N and W both leave the board."""
    with pytest.raises(OutOfBoundsMoveError, match="leaves the"):
        validate_move(cop_state, Direction.N, shared_config)
    with pytest.raises(OutOfBoundsMoveError):
        validate_move(cop_state, Direction.W, shared_config)


def test_moving_off_the_south_edge_is_rejected(thief_state, shared_config):
    at_edge = place_at(thief_state, 6, 6)
    with pytest.raises(OutOfBoundsMoveError):
        validate_move(at_edge, Direction.S, shared_config)
    with pytest.raises(OutOfBoundsMoveError):
        validate_move(at_edge, Direction.E, shared_config)


def test_moving_into_a_barrier_is_rejected(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3)])
    with pytest.raises(BlockedCellError, match="impassable to both"):
        validate_move(walled, Direction.N, shared_config)


def test_barriers_block_the_cop_too(cop_state, shared_config):
    """A barrier is impassable to both players (PDF p. 37)."""
    walled = wall_in(place_at(cop_state, 3, 3), [(3, 4)])
    with pytest.raises(BlockedCellError):
        validate_move(walled, Direction.E, shared_config)


def test_diagonals_have_no_representation():
    """E-13/E-14: an illegal move should be unspeakable, not merely rejected."""
    assert {d.value for d in Direction} == {"N", "S", "E", "W", "STAY"}
    with pytest.raises(ValueError):
        Direction("NE")


def test_move_outside_the_agreed_move_set_is_rejected(
    thief_state, valid_shared
):
    """Validation reads the move set from config rather than assuming it."""
    from police_thief.config.loader import build_shared_config

    # move_set is FIXED, so this config could never be loaded from disk -- the
    # object is built directly to prove validation consults it.
    config = build_shared_config(valid_shared)
    object.__setattr__(
        config.movement_and_barriers, "move_set", ("N", "S", "STAY")
    )
    with pytest.raises(IllegalMoveError, match="not in the agreed move set"):
        validate_move(thief_state, Direction.E, config)


# ----------------------------------------------------------------------
# Legal-action generation
# ----------------------------------------------------------------------


def test_legal_moves_have_a_fixed_deterministic_order(thief_state, shared_config):
    """STAY first, then N, S, E, W -- so two peers enumerate identically."""
    assert [m.direction for m in legal_moves(thief_state, shared_config)] == [
        Direction.STAY,
        Direction.N,
        Direction.S,
        Direction.E,
        Direction.W,
    ]


def test_legal_moves_are_stable_across_repeated_calls(thief_state, shared_config):
    first = legal_moves(thief_state, shared_config)
    for _ in range(10):
        assert legal_moves(thief_state, shared_config) == first


def test_legal_moves_exclude_off_board_directions(cop_state, shared_config):
    """From the corner [0,0] only STAY, S and E remain."""
    assert [m.direction for m in legal_moves(cop_state, shared_config)] == [
        Direction.STAY,
        Direction.S,
        Direction.E,
    ]


def test_legal_moves_exclude_barriered_directions(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3), (3, 4)])
    directions = [m.direction for m in legal_moves(walled, shared_config)]
    assert Direction.N not in directions
    assert Direction.E not in directions
    assert Direction.S in directions and Direction.W in directions


def test_every_generated_move_is_actually_legal(thief_state, shared_config):
    walled = wall_in(place_at(thief_state, 1, 1), [(0, 1), (1, 2)])
    for move in legal_moves(walled, shared_config):
        assert validate_move(walled, move.direction, shared_config) is not None


def test_legal_relocations_exclude_stay(thief_state, shared_config):
    """E-47 is about adjacent cells; STAY does not rescue a walled-in thief."""
    relocations = legal_relocations(thief_state, shared_config)
    assert Move(Direction.STAY) not in relocations
    assert len(relocations) == 4


def test_thief_is_not_trapped_in_the_open(thief_state, shared_config):
    assert not is_trapped(thief_state, shared_config)


def test_thief_walled_in_on_all_four_sides_is_trapped(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3), (4, 3), (3, 4), (3, 2)])
    assert is_trapped(walled, shared_config)
    # STAY is still a legal *move*, which is precisely why the trapped test
    # asks about relocations instead.
    assert Move(Direction.STAY) in legal_moves(walled, shared_config)
    assert legal_relocations(walled, shared_config) == ()


def test_thief_in_a_corner_needs_only_two_barriers_to_be_trapped(
    thief_state, shared_config
):
    """Board edges count towards imprisonment, per E-47's parenthetical."""
    cornered = wall_in(place_at(thief_state, 0, 0), [(1, 0), (0, 1)])
    assert is_trapped(cornered, shared_config)


def test_thief_has_no_barrier_actions(thief_state, shared_config):
    """Only the cop may place barriers (PDF p. 37)."""
    assert legal_actions(thief_state, shared_config) == legal_moves(
        thief_state, shared_config
    )
