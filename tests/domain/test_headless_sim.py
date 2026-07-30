"""The headless harness: full sub-games, termination, and legality throughout."""

from __future__ import annotations

import pytest

from police_thief.config.loader import build_shared_config
from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason, Direction, Role, TerminalReason
from police_thief.domain.exceptions import GameAlreadyFinishedError
from police_thief.domain.rules import validate_action
from police_thief.sim.harness import MatchHarness
from police_thief.sim.headless import main as headless_main
from police_thief.sim.policies import (
    cycle_directions,
    first_legal_move,
    stay_put,
)


# ----------------------------------------------------------------------
# A full sub-game
# ----------------------------------------------------------------------


def test_full_sub_game_completes_and_terminates(shared_config):
    outcome = MatchHarness(shared_config).run(first_legal_move, cycle_directions)
    assert outcome.terminal is not None
    assert outcome.turns >= 1


def test_two_passive_agents_reach_the_survival_threshold(shared_config):
    """The cop starts in a corner and the thief in the centre; neither moves."""
    outcome = MatchHarness(shared_config).run(stay_put, stay_put)
    assert outcome.terminal.reason is TerminalReason.SURVIVAL
    assert outcome.terminal.winner is Role.THIEF
    assert outcome.turns == shared_config.movement_and_barriers.survival_threshold
    assert outcome.score.thief == shared_config.scoring.survival_thief
    assert outcome.score.cop == shared_config.scoring.survival_cop


def test_simulation_is_bounded_by_the_configured_ceiling(shared_config):
    outcome = MatchHarness(shared_config).run(stay_put, stay_put)
    assert outcome.turns <= shared_config.movement_and_barriers.max_moves


def test_simulation_terminates_on_a_short_configuration(valid_shared):
    """A tighter threshold must end the game sooner -- no infinite loop."""
    valid_shared["movement_and_barriers"]["survival_threshold"] = 35
    valid_shared["movement_and_barriers"]["max_moves"] = 36
    config = build_shared_config(valid_shared)
    outcome = MatchHarness(config).run(stay_put, stay_put)
    assert outcome.turns == 35


def test_every_applied_action_was_legal(shared_config):
    """Replay the history against a fresh harness, validating each action."""
    outcome = MatchHarness(shared_config).run(first_legal_move, cycle_directions)
    replay = MatchHarness(shared_config)
    for record in outcome.history:
        validate_action(replay.cop, record.cop_action, shared_config)
        if replay.is_finished:
            break
        replay.play_turn(record.cop_action, record.thief_action)
    assert replay.cop.terminal == outcome.terminal


def test_the_run_is_reproducible(shared_config):
    """Deterministic policies plus a deterministic domain give one outcome."""
    first = MatchHarness(shared_config).run(first_legal_move, cycle_directions)
    second = MatchHarness(shared_config).run(first_legal_move, cycle_directions)
    assert first.terminal == second.terminal
    assert first.score == second.score
    assert [str(r.cop_action) for r in first.history] == [
        str(r.cop_action) for r in second.history
    ]


def test_no_turn_may_follow_a_terminal_state(shared_config):
    harness = MatchHarness(shared_config)
    harness.run(stay_put, stay_put)
    with pytest.raises(GameAlreadyFinishedError):
        harness.play_turn(Move(Direction.STAY), Move(Direction.STAY))


def test_states_remain_separate_objects(shared_config):
    harness = MatchHarness(shared_config)
    harness.play_turn(Move(Direction.S), Move(Direction.N))
    assert harness.cop is not harness.thief
    assert harness.cop.role is Role.POLICE
    assert harness.thief.role is Role.THIEF
    assert harness.cop.position != harness.thief.position


# ----------------------------------------------------------------------
# Capture demonstrations
# ----------------------------------------------------------------------


def test_cop_walks_onto_the_thief_and_captures(shared_config):
    """The cop is steered next to a stationary thief, then steps onto it."""
    harness = MatchHarness(shared_config)
    # Cop [0,0] -> [3,2]; thief stays at [3,3].
    for direction in (Direction.S, Direction.S, Direction.S, Direction.E, Direction.E):
        harness.play_turn(Move(direction), Move(Direction.STAY))
    assert harness.cop_cell == Coordinate(3, 2)
    assert not harness.is_finished

    record = harness.play_turn(Move(Direction.E), Move(Direction.STAY))
    assert record.terminal is not None
    assert record.terminal.reason is TerminalReason.CAPTURE
    assert record.terminal.capture_reason is CaptureReason.COP_LANDED_ON_THIEF
    assert record.terminal.winner is Role.POLICE


def test_barrier_placed_on_the_thief_cell_captures(shared_config):
    """E-46: capture at the moment of placement, before the thief acts."""
    harness = MatchHarness(shared_config)
    for direction in (Direction.S, Direction.S, Direction.S, Direction.E, Direction.E):
        harness.play_turn(Move(direction), Move(Direction.STAY))
    assert harness.cop_cell == Coordinate(3, 2)

    record = harness.play_turn(
        PlaceBarrier(Coordinate(3, 3)), Move(Direction.STAY)
    )
    assert record.terminal.reason is TerminalReason.CAPTURE
    assert record.terminal.capture_reason is CaptureReason.BARRIER_ON_THIEF
    assert record.terminal.winner is Role.POLICE
    # The cop did not move to place it.
    assert harness.cop_cell == Coordinate(3, 2)


def test_thief_with_no_legal_move_is_captured(shared_config):
    """E-47: walled into a corner by barriers and board edges."""
    harness = MatchHarness(shared_config)

    # Put the thief in the corner [0,6] and the cop beside it, then wall it in.
    harness.thief = harness.thief.with_position(Coordinate(0, 6))
    harness.cop = harness.cop.with_position(Coordinate(1, 6))

    # Cop blocks [1,6]'s neighbour [0,5] indirectly: first block [1,6]->N is the
    # thief. Place at [1,6] own cell? Instead block [0,5] from [1,5].
    harness.cop = harness.cop.with_position(Coordinate(1, 5))
    record = harness.play_turn(PlaceBarrier(Coordinate(0, 5)), Move(Direction.STAY))
    assert record.terminal is None  # thief can still go S to [1,6]

    record = harness.play_turn(PlaceBarrier(Coordinate(1, 5)), Move(Direction.STAY))
    assert record.terminal is None

    # Now block [1,6], the thief's only remaining escape.
    harness.cop = harness.cop.with_position(Coordinate(2, 6))
    record = harness.play_turn(PlaceBarrier(Coordinate(1, 6)), Move(Direction.STAY))

    assert record.terminal is not None
    assert record.terminal.reason is TerminalReason.CAPTURE
    assert record.terminal.capture_reason is CaptureReason.THIEF_HAS_NO_LEGAL_MOVE


def test_capture_scores_the_configured_amounts(shared_config):
    harness = MatchHarness(shared_config)
    for direction in (Direction.S, Direction.S, Direction.S, Direction.E, Direction.E):
        harness.play_turn(Move(direction), Move(Direction.STAY))
    harness.play_turn(Move(Direction.E), Move(Direction.STAY))

    from police_thief.domain.scoring import calculate_score

    score = calculate_score(harness.cop.terminal, shared_config)
    assert score.cop == shared_config.scoring.capture_cop
    assert score.thief == shared_config.scoring.capture_thief


# ----------------------------------------------------------------------
# The CLI
# ----------------------------------------------------------------------


def test_headless_cli_runs_and_reports(capsys, shared_path):
    code = headless_main(["--shared", str(shared_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "headless sub-game" in out
    assert "result" in out
    assert "no opponent position in either peer's state" in out


def test_headless_cli_is_deterministic(capsys, shared_path):
    headless_main(["--shared", str(shared_path)])
    first = capsys.readouterr().out
    headless_main(["--shared", str(shared_path)])
    assert capsys.readouterr().out == first


def test_headless_cli_reports_config_errors(capsys, tmp_path):
    code = headless_main(["--shared", str(tmp_path / "absent.json")])
    assert code == 1
    assert "ConfigFileNotFoundError" in capsys.readouterr().err
