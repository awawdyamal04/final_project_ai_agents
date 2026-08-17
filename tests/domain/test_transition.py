"""Transition determinism, purity, and failure atomicity."""

from __future__ import annotations

import pytest

from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction
from police_thief.domain.exceptions import (
    BlockedCellError,
    InvalidBarrierPlacementError,
    OutOfBoundsMoveError,
)
from police_thief.domain.transition import apply_action
from tests.domain.conftest import wall_in


def test_same_input_produces_the_same_output(thief_state, shared_config):
    """Determinism is what lets a replay re-derive a match from a move list."""
    results = [
        apply_action(thief_state, Move(Direction.N), shared_config)
        for _ in range(10)
    ]
    assert all(r.state == results[0].state for r in results)
    assert all(r.events == results[0].events for r in results)


def test_input_state_is_not_mutated(thief_state, shared_config):
    before = thief_state
    before_position = thief_state.position
    apply_action(thief_state, Move(Direction.N), shared_config)
    assert thief_state == before
    assert thief_state.position == before_position


def test_transition_returns_a_new_object(thief_state, shared_config):
    result = apply_action(thief_state, Move(Direction.N), shared_config)
    assert result.state is not thief_state
    assert result.state.position == Coordinate(2, 3)


def test_board_is_shared_not_copied_when_unchanged(thief_state, shared_config):
    """A move does not touch the board, so the object may be reused."""
    result = apply_action(thief_state, Move(Direction.N), shared_config)
    assert result.state.board == thief_state.board


@pytest.mark.parametrize(
    ("action", "error"),
    [
        (Move(Direction.N), OutOfBoundsMoveError),
        (PlaceBarrier(Coordinate(5, 5)), InvalidBarrierPlacementError),
    ],
)
def test_illegal_action_does_not_partially_modify_state(
    cop_state, shared_config, action, error
):
    """Validation precedes application; nothing is half-applied."""
    snapshot = cop_state
    with pytest.raises(error):
        apply_action(cop_state, action, shared_config)
    assert cop_state == snapshot
    assert cop_state.position == snapshot.position
    assert cop_state.board.barriers == frozenset()
    assert cop_state.barriers_placed == 0
    assert cop_state.turn == snapshot.turn


def test_blocked_move_does_not_modify_state(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3)])
    snapshot = walled
    with pytest.raises(BlockedCellError):
        apply_action(walled, Move(Direction.N), shared_config)
    assert walled == snapshot


def test_events_are_deterministic_and_ordered(cop_state, shared_config):
    result = apply_action(cop_state, Move(Direction.S), shared_config)
    (event,) = result.events
    payload = event.to_dict()
    assert payload["event"] == "agent_moved"
    assert payload["direction"] == "S"
    assert payload["origin"] == [0, 0]
    assert payload["destination"] == [1, 0]

    again = apply_action(cop_state, Move(Direction.S), shared_config)
    assert [e.to_dict() for e in again.events] == [payload]


def test_stay_still_emits_a_move_event(thief_state, shared_config):
    """Standing still is an action taken, not an absence of one."""
    result = apply_action(thief_state, Move(Direction.STAY), shared_config)
    (event,) = result.events
    assert event.to_dict()["direction"] == "STAY"
    assert result.state.position == thief_state.position


def test_barrier_transition_reports_the_cell_for_adjudication(
    cop_state, shared_config
):
    """The transition does not evaluate E-46 itself -- it lacks the input."""
    result = apply_action(cop_state, PlaceBarrier(Coordinate(0, 1)), shared_config)
    assert result.barrier_cell == Coordinate(0, 1)
    assert result.terminal is None  # capture is the adjudicator's call


def test_move_transition_reports_no_barrier_cell(thief_state, shared_config):
    assert apply_action(thief_state, Move(Direction.N), shared_config).barrier_cell is None


def test_transition_has_no_opponent_parameter():
    """The signature itself is the guarantee."""
    import inspect

    params = set(inspect.signature(apply_action).parameters)
    assert params == {"state", "action", "config"}
    for banned in ("opponent", "opponent_cell", "opponent_position", "world"):
        assert banned not in params


def test_a_sequence_of_transitions_is_reproducible(cop_state, shared_config):
    """Replaying the same action list must land in the same place."""

    def run():
        state = cop_state
        for action in (
            Move(Direction.S),
            Move(Direction.E),
            PlaceBarrier(Coordinate(1, 2)),
            Move(Direction.S),
        ):
            state = apply_action(state, action, shared_config).state
        return state

    first, second = run(), run()
    assert first == second
    assert first.position == Coordinate(2, 1)
    assert first.board.barriers == frozenset({Coordinate(1, 2)})
