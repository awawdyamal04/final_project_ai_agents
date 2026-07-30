"""The three mandatory capture conditions, and the unresolved edge cases."""

from __future__ import annotations

import pytest

from police_thief.domain.capture import (
    evaluate_barrier_capture,
    evaluate_full_turn_capture,
    evaluate_movement_capture,
    evaluate_trapped_capture,
)
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason, Role
from police_thief.domain.simultaneity import (
    DEFAULT_SIMULTANEITY_POLICY,
    PostMovePositionsOnly,
    TurnMovement,
)
from police_thief.domain.terminal import capture as terminal_capture
from tests.domain.conftest import place_at, wall_in


def movement(cop_before, cop_after, thief_before, thief_after) -> TurnMovement:
    return TurnMovement(
        cop_before=Coordinate(*cop_before),
        cop_after=Coordinate(*cop_after),
        thief_before=Coordinate(*thief_before),
        thief_after=Coordinate(*thief_after),
    )


# ----------------------------------------------------------------------
# 1. Cop lands on the thief's cell (Ch. 3, PDF p. 38)
# ----------------------------------------------------------------------


def test_cop_landing_on_the_thief_is_a_capture():
    verdict = evaluate_movement_capture(movement((3, 2), (3, 3), (3, 3), (3, 3)))
    assert verdict.captured
    assert verdict.reason is CaptureReason.COP_LANDED_ON_THIEF


def test_no_capture_when_cells_differ():
    verdict = evaluate_movement_capture(movement((0, 0), (0, 1), (3, 3), (3, 4)))
    assert not verdict.captured
    assert verdict.reason is None


def test_adjacent_is_not_captured():
    """One step away is not the same cell."""
    assert not evaluate_movement_capture(
        movement((3, 2), (3, 2), (3, 3), (3, 3))
    ).captured


def test_both_moving_to_the_same_cell_is_a_capture():
    """The one edge case every reading agrees on."""
    verdict = evaluate_movement_capture(movement((3, 2), (3, 3), (3, 4), (3, 3)))
    assert verdict.captured


# ----------------------------------------------------------------------
# 2. Barrier on the thief's cell -- E-46
# ----------------------------------------------------------------------


def test_barrier_on_the_thief_cell_is_a_capture():
    verdict = evaluate_barrier_capture(Coordinate(3, 3), Coordinate(3, 3))
    assert verdict.captured
    assert verdict.reason is CaptureReason.BARRIER_ON_THIEF


def test_barrier_elsewhere_is_not_a_capture():
    assert not evaluate_barrier_capture(Coordinate(3, 4), Coordinate(3, 3)).captured


# ----------------------------------------------------------------------
# 3. Thief with no legal move -- E-47
# ----------------------------------------------------------------------


def test_thief_walled_in_on_four_sides_is_captured(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3), (4, 3), (3, 4), (3, 2)])
    verdict = evaluate_trapped_capture(walled, shared_config)
    assert verdict.captured
    assert verdict.reason is CaptureReason.THIEF_HAS_NO_LEGAL_MOVE


def test_board_edges_count_towards_imprisonment(thief_state, shared_config):
    """E-47's parenthetical: barriers *and/or* board edges."""
    cornered = wall_in(place_at(thief_state, 0, 0), [(1, 0), (0, 1)])
    assert evaluate_trapped_capture(cornered, shared_config).captured


def test_thief_with_one_escape_is_not_captured(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3), (4, 3), (3, 4)])
    assert not evaluate_trapped_capture(walled, shared_config).captured


def test_stay_does_not_rescue_a_walled_in_thief(thief_state, shared_config):
    """The rule counts adjacent cells, not available actions."""
    from police_thief.domain.rules import legal_moves

    walled = wall_in(thief_state, [(2, 3), (4, 3), (3, 4), (3, 2)])
    assert legal_moves(walled, shared_config)  # STAY is still legal
    assert evaluate_trapped_capture(walled, shared_config).captured


def test_open_board_thief_is_never_captured_by_imprisonment(
    thief_state, shared_config
):
    assert not evaluate_trapped_capture(thief_state, shared_config).captured


# ----------------------------------------------------------------------
# Ordering and terminal construction
# ----------------------------------------------------------------------


def test_movement_capture_takes_precedence_over_imprisonment(
    thief_state, shared_config
):
    """A thief caught by coincidence is caught for that reason."""
    walled = wall_in(place_at(thief_state, 3, 3), [(2, 3), (4, 3), (3, 4), (3, 2)])
    verdict = evaluate_full_turn_capture(
        movement((3, 2), (3, 3), (3, 3), (3, 3)), walled, shared_config
    )
    assert verdict.reason is CaptureReason.COP_LANDED_ON_THIEF


def test_capture_terminal_records_reason_winner_and_turn():
    terminal = terminal_capture(12, CaptureReason.BARRIER_ON_THIEF)
    assert terminal.is_capture
    assert terminal.winner is Role.POLICE
    assert terminal.turn == 12
    assert terminal.capture_reason is CaptureReason.BARRIER_ON_THIEF
    assert terminal.to_dict()["capture_reason"] == "barrier_on_thief"


# ----------------------------------------------------------------------
# Unresolved cases -- these encode our reading, not the PDF's ruling
# ----------------------------------------------------------------------


def test_default_policy_is_documented_as_our_reading():
    assert isinstance(DEFAULT_SIMULTANEITY_POLICY, PostMovePositionsOnly)
    assert DEFAULT_SIMULTANEITY_POLICY.name == "post_move_positions_only"


def test_cell_swap_is_not_a_capture_under_the_default_policy():
    """UNRESOLVED (Q-9). An opponent may reasonably read this the other way."""
    assert not evaluate_movement_capture(
        movement((3, 2), (3, 3), (3, 3), (3, 2))
    ).captured


def test_swap_is_recognised_as_such():
    assert movement((3, 2), (3, 3), (3, 3), (3, 2)).is_swap


def test_entering_a_vacated_cell_is_not_a_capture_under_the_default_policy():
    """UNRESOLVED (Q-9)."""
    move = movement((3, 2), (3, 3), (3, 3), (3, 4))
    assert move.cop_entered_vacated_cell
    assert not evaluate_movement_capture(move).captured


def test_thief_moving_onto_the_cop_is_a_capture_under_the_default_policy():
    """UNRESOLVED (Q-9), and the least defensible of the four readings.

    The PDF phrases capture as *the cop* landing on the thief; coincidence is
    symmetric, so this reading lets a thief lose by blundering into the cop.
    Worth raising explicitly in negotiation.
    """
    assert evaluate_movement_capture(
        movement((3, 3), (3, 3), (3, 2), (3, 3))
    ).captured


def test_an_alternative_policy_changes_the_outcome():
    """The whole point of isolating this behind an interface."""

    class SwapCountsAsCapture:
        name = "swap_counts"

        def resolve(self, mv: TurnMovement):
            if mv.positions_coincide or mv.is_swap:
                return CaptureReason.COP_LANDED_ON_THIEF
            return None

    swap = movement((3, 2), (3, 3), (3, 3), (3, 2))
    assert not evaluate_movement_capture(swap).captured
    assert evaluate_movement_capture(swap, SwapCountsAsCapture()).captured
