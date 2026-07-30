"""Coordinates and board geometry."""

from __future__ import annotations

import pytest

from police_thief.config.loader import build_shared_config
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction
from police_thief.domain.exceptions import InvalidCoordinateError


# ----------------------------------------------------------------------
# Coordinates
# ----------------------------------------------------------------------


def test_coordinate_is_frozen_and_hashable():
    cell = Coordinate(2, 3)
    with pytest.raises(Exception):
        cell.row = 5  # type: ignore[misc]
    assert {Coordinate(2, 3), Coordinate(2, 3)} == {Coordinate(2, 3)}


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        (Direction.N, Coordinate(1, 2)),
        (Direction.S, Coordinate(3, 2)),
        (Direction.E, Coordinate(2, 3)),
        (Direction.W, Coordinate(2, 1)),
        (Direction.STAY, Coordinate(2, 2)),
    ],
)
def test_shift_follows_the_documented_axis_convention(direction, expected):
    """Origin top-left, vertical axis growing downward: N decreases the row."""
    assert Coordinate(2, 2).shifted(direction) == expected


def test_manhattan_distance():
    assert Coordinate(2, 2).manhattan_distance_to(Coordinate(5, 5)) == 6
    assert Coordinate(0, 0).manhattan_distance_to(Coordinate(0, 0)) == 0


def test_orthogonal_adjacency_excludes_diagonals():
    origin = Coordinate(3, 3)
    assert origin.is_orthogonally_adjacent_to(Coordinate(3, 4))
    assert origin.is_orthogonally_adjacent_to(Coordinate(2, 3))
    assert not origin.is_orthogonally_adjacent_to(Coordinate(4, 4))
    assert not origin.is_orthogonally_adjacent_to(Coordinate(3, 3))


def test_coordinate_ordering_is_stable():
    cells = [Coordinate(1, 2), Coordinate(0, 5), Coordinate(1, 0)]
    assert sorted(cells) == [Coordinate(0, 5), Coordinate(1, 0), Coordinate(1, 2)]


def test_round_trip_through_config_pair_form():
    assert Coordinate.from_pair([3, 3]) == Coordinate(3, 3)
    assert Coordinate(3, 3).as_list() == [3, 3]


# ----------------------------------------------------------------------
# Board
# ----------------------------------------------------------------------


def test_board_dimensions_come_from_config(shared_config):
    board = Board.from_config(shared_config)
    assert board.size == shared_config.grid_size == 7
    assert board.min_index == 0
    assert board.max_index == 6
    assert board.cell_count == 49


def test_board_respects_a_nonzero_axis_start_index(valid_shared):
    """A 1-indexed board is negotiable; bounds must move with it."""
    valid_shared["board_and_agents"]["axis_start_index"] = 1
    valid_shared["board_and_agents"]["cop_start"] = [1, 1]
    valid_shared["board_and_agents"]["thief_start"] = [4, 4]
    board = Board.from_config(build_shared_config(valid_shared))

    assert board.min_index == 1
    assert board.max_index == 7
    assert board.contains(Coordinate(1, 1))
    assert board.contains(Coordinate(7, 7))
    assert not board.contains(Coordinate(0, 0))
    assert not board.contains(Coordinate(8, 8))


@pytest.mark.parametrize(
    "cell",
    [Coordinate(-1, 0), Coordinate(0, -1), Coordinate(7, 0), Coordinate(0, 7)],
)
def test_out_of_bounds_coordinates_are_rejected(shared_config, cell):
    board = Board.from_config(shared_config)
    assert not board.contains(cell)
    with pytest.raises(InvalidCoordinateError, match="outside"):
        board.require_contains(cell)


def test_board_has_no_barriers_initially(shared_config):
    """The PDF defines no pre-placed static obstacles; only cop barriers."""
    assert Board.from_config(shared_config).barriers == frozenset()


def test_placing_a_barrier_returns_a_new_board(shared_config):
    board = Board.from_config(shared_config)
    blocked = board.with_barrier(Coordinate(2, 2))

    assert board.barriers == frozenset()      # original untouched
    assert blocked.is_blocked(Coordinate(2, 2))
    assert not blocked.is_passable(Coordinate(2, 2))
    assert blocked.barrier_count == 1


def test_barrier_cannot_be_stacked(shared_config):
    board = Board.from_config(shared_config).with_barrier(Coordinate(2, 2))
    with pytest.raises(InvalidCoordinateError, match="already holds"):
        board.with_barrier(Coordinate(2, 2))


def test_barrier_outside_the_board_is_rejected(shared_config):
    board = Board.from_config(shared_config)
    with pytest.raises(InvalidCoordinateError, match="outside"):
        board.with_barrier(Coordinate(9, 9))


def test_neighbours_are_in_fixed_nsew_order(shared_config):
    board = Board.from_config(shared_config)
    assert board.neighbours(Coordinate(3, 3)) == (
        Coordinate(2, 3),  # N
        Coordinate(4, 3),  # S
        Coordinate(3, 4),  # E
        Coordinate(3, 2),  # W
    )


def test_neighbours_are_clipped_at_the_edge(shared_config):
    board = Board.from_config(shared_config)
    assert board.neighbours(Coordinate(0, 0)) == (Coordinate(1, 0), Coordinate(0, 1))
    assert len(board.neighbours(Coordinate(6, 6))) == 2


def test_neighbours_include_blocked_cells_but_passable_neighbours_do_not(
    shared_config,
):
    """The distinction is what makes E-47 expressible."""
    board = Board.from_config(shared_config).with_barrier(Coordinate(2, 3))
    assert Coordinate(2, 3) in board.neighbours(Coordinate(3, 3))
    assert Coordinate(2, 3) not in board.passable_neighbours(Coordinate(3, 3))


def test_placement_targets_are_own_cell_then_neighbours(shared_config):
    board = Board.from_config(shared_config)
    assert board.placement_targets(Coordinate(3, 3)) == (
        Coordinate(3, 3),
        Coordinate(2, 3),
        Coordinate(4, 3),
        Coordinate(3, 4),
        Coordinate(3, 2),
    )


def test_placement_targets_exclude_already_blocked_cells(shared_config):
    board = Board.from_config(shared_config).with_barrier(Coordinate(2, 3))
    assert Coordinate(2, 3) not in board.placement_targets(Coordinate(3, 3))


def test_all_cells_is_row_major_and_complete(shared_config):
    board = Board.from_config(shared_config)
    cells = list(board.all_cells())
    assert len(cells) == 49
    assert cells[0] == Coordinate(0, 0)
    assert cells[1] == Coordinate(0, 1)
    assert cells[-1] == Coordinate(6, 6)


def test_direction_between_adjacent_cells(shared_config):
    board = Board.from_config(shared_config)
    assert board.direction_between(Coordinate(3, 3), Coordinate(2, 3)) is Direction.N
    assert board.direction_between(Coordinate(3, 3), Coordinate(3, 3)) is Direction.STAY
    # Diagonal and distant cells have no single direction.
    assert board.direction_between(Coordinate(3, 3), Coordinate(4, 4)) is None
    assert board.direction_between(Coordinate(3, 3), Coordinate(3, 5)) is None
