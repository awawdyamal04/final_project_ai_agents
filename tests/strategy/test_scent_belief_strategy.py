"""Scent, belief and the two heuristic strategies."""

from __future__ import annotations

import pytest

from police_thief.config.loader import load_shared_config
from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.belief import BeliefMap
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role
from police_thief.domain.rules import validate_action
from police_thief.domain.scent import SIGMA, ScentField, ScentModel
from police_thief.domain.state import LocalState
from police_thief.strategy.base import LocalView
from police_thief.strategy.heuristics import CopStrategy, ThiefStrategy
from police_thief.strategy.tracker import OpponentTracker
from tests.conftest import SHARED_CONFIG_PATH


@pytest.fixture
def cfg():
    return load_shared_config(SHARED_CONFIG_PATH)


@pytest.fixture
def board(cfg):
    return Board.from_config(cfg)


def view_for(cfg, board, role, cell, *, belief=None, scent=None, recent=()):
    state = LocalState.initial(role, cfg).with_position(cell).with_board(board)
    return LocalView(
        state=state,
        config=cfg,
        belief=belief or BeliefMap.uniform(board),
        opponent_scent=scent or ScentField.for_config(cfg, board),
        recent_cells=tuple(recent),
    )


# ----------------------------------------------------------------------
# Scent
# ----------------------------------------------------------------------


def test_emission_reproduces_the_specified_field(cfg, board):
    """The tabulated 5x5 field: 0.90 / 0.62 / 0.42 / 0.20 / 0.14 / 0.04."""
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(3, 3))

    assert round(scent.intensity_at(Coordinate(3, 3)), 2) == 0.90
    assert round(scent.intensity_at(Coordinate(2, 3)), 2) == 0.62   # d^2 = 1
    assert round(scent.intensity_at(Coordinate(2, 2)), 2) == 0.42   # d^2 = 2
    assert round(scent.intensity_at(Coordinate(1, 3)), 2) == 0.20   # d^2 = 4
    assert round(scent.intensity_at(Coordinate(1, 2)), 2) == 0.14   # d^2 = 5
    assert round(scent.intensity_at(Coordinate(1, 1)), 2) == 0.04   # d^2 = 8


def test_emission_parameters_come_from_config(cfg):
    model = ScentModel.from_config(cfg)
    assert model.center_intensity == cfg.pheromones.pheromone_center_intensity
    assert model.decay == cfg.pheromones.pheromone_decay
    assert model.window == cfg.pheromones.pheromone_grid_size == 5
    assert model.radius == 2
    assert model.sigma == SIGMA


def test_emission_is_clipped_at_the_board_edge(cfg, board):
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(0, 0))
    assert all(board.contains(c) for c in scent.values)


def test_decay_applies_the_configured_rate(cfg, board):
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(3, 3))
    before = scent.intensity_at(Coordinate(3, 3))

    scent.decay()
    assert scent.intensity_at(Coordinate(3, 3)) == pytest.approx(
        before * (1.0 - cfg.pheromones.pheromone_decay)
    )


def test_decay_matches_the_numeric_example(cfg):
    """0.9 decayed once at rho = 0.10 gives 0.81 -- the example E-23 locks."""
    example = ScentModel.from_config(cfg).numeric_example()
    assert example["centre"] == 0.9
    assert example["after_one_decay_turn"] == 0.81


def test_scent_never_goes_negative_and_fades_away(cfg, board):
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(3, 3))
    for _ in range(400):
        scent.decay()
    assert scent.total() >= 0.0
    assert scent.total() == pytest.approx(0.0, abs=1e-6)


def test_a_trail_is_still_readable_after_a_few_turns(cfg, board):
    """Slow decay is the point: the trail must outlive the step that made it."""
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(3, 3))
    for _ in range(6):
        scent.decay()
    assert scent.intensity_at(Coordinate(3, 3)) > 0.45 * 0.9


def test_scent_cannot_be_planted_away_from_the_emitter(cfg, board):
    """The only deposit API takes the emitter's own cell."""
    scent = ScentField.for_config(cfg, board)
    assert not hasattr(scent, "plant")
    assert not hasattr(scent, "forge")
    scent.emit(Coordinate(0, 0))
    assert scent.intensity_at(Coordinate(6, 6)) == 0.0


def test_repeated_occupation_strengthens_the_trail(cfg, board):
    scent = ScentField.for_config(cfg, board)
    scent.advance_turn(Coordinate(3, 3))
    once = scent.intensity_at(Coordinate(3, 3))
    scent.advance_turn(Coordinate(3, 3))
    assert scent.intensity_at(Coordinate(3, 3)) > once


# ----------------------------------------------------------------------
# Belief
# ----------------------------------------------------------------------


def test_uniform_belief_is_normalised_and_excludes_barriers(cfg, board):
    walled = board.with_barrier(Coordinate(2, 2))
    belief = BeliefMap.uniform(walled)
    assert belief.is_normalised()
    assert belief.probability_at(Coordinate(2, 2)) == 0.0


def test_belief_stays_normalised_through_the_whole_cycle(cfg, board):
    belief = BeliefMap.uniform(board)
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(4, 4))

    for _ in range(10):
        belief.predict(None)
        belief.update_from_scent(scent)
        belief.exclude_impossible(disproven={Coordinate(0, 0)})
        assert belief.is_normalised()


def test_impossible_cells_are_removed(cfg, board):
    walled = board.with_barrier(Coordinate(3, 4))
    belief = BeliefMap.uniform(walled)
    belief.exclude_impossible(disproven={Coordinate(1, 1)})

    assert belief.probability_at(Coordinate(3, 4)) == 0.0
    assert belief.probability_at(Coordinate(1, 1)) == 0.0
    assert belief.is_normalised()


def test_belief_update_from_scent_favours_the_trail(cfg, board):
    belief = BeliefMap.uniform(board)
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(5, 5))

    before = belief.probability_at(Coordinate(5, 5))
    belief.update_from_scent(scent)

    assert belief.probability_at(Coordinate(5, 5)) > before
    assert belief.peak() == Coordinate(5, 5)
    assert belief.is_normalised()


def test_predict_with_a_known_direction_shifts_the_mass(cfg, board):
    belief = BeliefMap.certain(board, Coordinate(3, 3))
    belief.predict(Direction.N)
    assert belief.peak() == Coordinate(2, 3)


def test_predict_without_a_direction_diffuses(cfg, board):
    belief = BeliefMap.certain(board, Coordinate(3, 3))
    belief.predict(None)
    assert belief.entropy_cells() == 5           # own cell + four neighbours
    assert belief.is_normalised()


def test_predict_does_not_walk_through_a_barrier(cfg, board):
    walled = board.with_barrier(Coordinate(2, 3))
    belief = BeliefMap.certain(walled, Coordinate(3, 3))
    belief.predict(Direction.N)
    assert belief.probability_at(Coordinate(2, 3)) == 0.0
    assert belief.peak() == Coordinate(3, 3)     # the step was impossible


def test_contradictory_evidence_resets_to_ignorance(cfg, board):
    """An empty belief is no basis for a decision; uniform is the honest state."""
    belief = BeliefMap.certain(board, Coordinate(3, 3))
    belief.exclude({Coordinate(3, 3)})
    assert belief.is_normalised()
    assert belief.entropy_cells() > 1


# ----------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.POLICE, Role.THIEF])
def test_strategy_always_returns_a_legal_action(cfg, board, role):
    strategy = CopStrategy() if role is Role.POLICE else ThiefStrategy()
    for row in range(7):
        for col in range(7):
            view = view_for(cfg, board, role, Coordinate(row, col))
            action = strategy.choose(view)
            validate_action(view.state, action, cfg)   # raises if illegal


@pytest.mark.parametrize("role", [Role.POLICE, Role.THIEF])
def test_strategy_is_deterministic(cfg, board, role):
    strategy = CopStrategy() if role is Role.POLICE else ThiefStrategy()
    view = view_for(cfg, board, role, Coordinate(3, 3))
    first = strategy.choose(view)
    assert all(strategy.choose(view) == first for _ in range(25))


def test_cop_moves_toward_the_belief_peak(cfg, board):
    belief = BeliefMap.certain(board, Coordinate(3, 6))
    view = view_for(cfg, board, Role.POLICE, Coordinate(3, 3), belief=belief)
    action = CopStrategy().choose(view)
    assert isinstance(action, Move)
    assert action.direction is Direction.E       # toward column 6


def test_cop_follows_scent_when_belief_is_flat(cfg, board):
    scent = ScentField.for_config(cfg, board)
    scent.emit(Coordinate(3, 6))
    view = view_for(cfg, board, Role.POLICE, Coordinate(3, 3), scent=scent)
    action = CopStrategy().choose(view)
    assert isinstance(action, Move)
    assert action.direction is not Direction.STAY


def test_cop_avoids_recently_visited_cells(cfg, board):
    """Loop avoidance: a cell just left is a worse choice than a fresh one."""
    belief = BeliefMap.uniform(board)
    here = Coordinate(3, 3)
    recent = (Coordinate(3, 2),) * 3
    action = CopStrategy().choose(
        view_for(cfg, board, Role.POLICE, here, belief=belief, recent=recent)
    )
    assert not (isinstance(action, Move) and action.direction is Direction.W)


def test_cop_does_not_spend_a_barrier_in_open_ground(cfg, board):
    """A quarry with four exits loses nothing to one barrier."""
    open_board = view_for(
        cfg, board, Role.POLICE, Coordinate(3, 3),
        belief=BeliefMap.certain(board, Coordinate(3, 4)),
    )
    assert not isinstance(CopStrategy().choose(open_board), PlaceBarrier)


def test_cop_closes_the_escape_when_the_thief_is_cornered(cfg, board):
    """Pursuit alone never closes at equal speed; barriers are the only way.

    Cop diagonally adjacent at (1,1), thief believed cornered at (0,0). The
    thief's only exits are (0,1) and (1,0), and both are within the cop's
    placement reach -- so the cop closes one rather than chasing.
    """
    view = view_for(
        cfg, board, Role.POLICE, Coordinate(1, 1),
        belief=BeliefMap.certain(board, Coordinate(0, 0)),
    )
    action = CopStrategy().choose(view)
    assert isinstance(action, PlaceBarrier)
    assert action.cell in (Coordinate(0, 1), Coordinate(1, 0))


def test_thief_moves_away_from_the_believed_cop(cfg, board):
    """Asserts the property, not one direction.

    On a Manhattan grid several moves can increase the distance equally -- from
    (3,3) with the cop at (3,1), both E and N gain exactly one. Pinning a single
    direction would be testing the tie-break, not the behaviour.
    """
    threat = Coordinate(3, 1)
    here = Coordinate(3, 3)
    belief = BeliefMap.certain(board, threat)
    view = view_for(cfg, board, Role.THIEF, here, belief=belief)

    action = ThiefStrategy().choose(view)
    assert isinstance(action, Move)
    destination = here.shifted(action.direction)
    assert destination.manhattan_distance_to(threat) > here.manhattan_distance_to(
        threat
    )


def test_thief_prefers_open_ground_to_a_corner(cfg, board):
    """Being boxed in loses outright, so freedom of movement is survival."""
    belief = BeliefMap.certain(board, Coordinate(6, 6))
    view = view_for(cfg, board, Role.THIEF, Coordinate(1, 1), belief=belief)
    action = ThiefStrategy().choose(view)
    destination = view.position.shifted(action.direction)
    assert len(board.passable_neighbours(destination)) >= 3


def test_thief_never_walks_into_a_barrier(cfg, board):
    walled = board
    for cell in (Coordinate(2, 3), Coordinate(3, 4), Coordinate(4, 3)):
        walled = walled.with_barrier(cell)
    view = view_for(cfg, walled, Role.THIEF, Coordinate(3, 3))
    action = ThiefStrategy().choose(view)
    validate_action(view.state, action, cfg)


def test_neither_strategy_can_see_the_opponent(cfg, board):
    """LocalView has no field that could hold a true position."""
    import dataclasses

    names = {f.name for f in dataclasses.fields(LocalView)}
    assert names == {
        "state", "config", "belief", "opponent_scent", "recent_cells"
    }
    for banned in (
        "opponent_position", "opponent_state", "harness", "global_state",
        "adjudicator", "true_position",
    ):
        assert banned not in names

    view = view_for(cfg, board, Role.POLICE, Coordinate(0, 0))
    for banned in ("opponent_position", "harness", "global_state"):
        assert not hasattr(view, banned)
        assert not hasattr(view.state, banned)


# ----------------------------------------------------------------------
# Tracker
# ----------------------------------------------------------------------


def test_tracker_seeds_from_the_agreed_start_cell(cfg, board):
    """Both start cells are signed shared conditions, not local truth."""
    tracker = OpponentTracker(role=Role.POLICE, config=cfg, board=board)
    assert tracker.belief.peak() == Coordinate.from_pair(
        cfg.board_and_agents.thief_start
    )
    assert tracker.belief.is_normalised()


def test_tracker_follows_a_revealed_move(cfg, board):
    tracker = OpponentTracker(role=Role.POLICE, config=cfg, board=board)
    tracker.observe_opponent_action(
        Move(Direction.N), own_cell=Coordinate(0, 0)
    )
    assert tracker.belief.is_normalised()
    assert tracker.opponent_scent.total() > 0.0


def test_tracker_excludes_our_own_cell(cfg, board):
    """If the opponent were here the turn would already have ended."""
    tracker = OpponentTracker(role=Role.POLICE, config=cfg, board=board)
    tracker.observe_opponent_action(
        Move(Direction.STAY), own_cell=Coordinate(3, 3)
    )
    assert tracker.belief.probability_at(Coordinate(3, 3)) == 0.0


def test_tracker_records_a_declared_barrier(cfg, board):
    tracker = OpponentTracker(role=Role.THIEF, config=cfg, board=board)
    tracker.observe_barrier(Coordinate(2, 2))
    assert tracker.board.is_blocked(Coordinate(2, 2))
    assert tracker.belief.probability_at(Coordinate(2, 2)) == 0.0


def test_tracker_keeps_recent_cells_bounded(cfg, board):
    tracker = OpponentTracker(role=Role.POLICE, config=cfg, board=board)
    for i in range(50):
        tracker.note_own_position(Coordinate(i % 7, 0))
    assert len(tracker.recent_cells) <= 8
