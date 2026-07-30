"""The information boundary: E-8 and E-9, enforced structurally.

These are the rules with the heaviest sanctions in the specification --
"disqualification of the project for an illegal advantage". They are also the
easiest to break by accident, because the opponent's position is exactly what
every part of the program would find convenient to know.

So these tests do not check that we *avoid displaying* the opponent's position.
They check that a live peer's state cannot *hold* one.
"""

from __future__ import annotations

import dataclasses
import inspect
import json

import pytest

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Role
from police_thief.domain.state import FORBIDDEN_STATE_FIELDS, LocalState
from police_thief.sim.harness import MatchHarness
from police_thief.sim.policies import cycle_directions, first_legal_move


# ----------------------------------------------------------------------
# The state object itself
# ----------------------------------------------------------------------


def test_local_state_fields_are_exactly_the_legal_set():
    """An exhaustive whitelist: anything new must be justified deliberately."""
    assert {f.name for f in dataclasses.fields(LocalState)} == {
        "role",
        "position",
        "board",
        "turn",
        "barriers_placed",
        "terminal",
    }


@pytest.mark.parametrize("name", sorted(FORBIDDEN_STATE_FIELDS))
def test_forbidden_field_names_are_absent(cop_state, name):
    assert not hasattr(cop_state, name)
    assert name not in {f.name for f in dataclasses.fields(LocalState)}


def test_opponent_position_attribute_does_not_exist(cop_state):
    """Not None, not Optional -- absent. A leak is an AttributeError."""
    with pytest.raises(AttributeError):
        _ = cop_state.opponent_position  # type: ignore[attr-defined]


def test_slots_prevent_attaching_an_opponent_position_at_runtime(cop_state):
    """slots=True closes the back door that a plain dataclass would leave open.

    The exact exception type varies -- frozen and slotted dataclasses reject the
    assignment through different paths -- so the assertion is that it fails and
    that the attribute still does not exist, not that it fails a particular way.
    """
    with pytest.raises(Exception):
        cop_state.opponent_position = Coordinate(3, 3)  # type: ignore[attr-defined]
    assert not hasattr(cop_state, "opponent_position")


def test_local_state_has_no_dict_to_smuggle_fields_into(cop_state):
    assert not hasattr(cop_state, "__dict__")


def test_state_is_frozen(cop_state):
    with pytest.raises(dataclasses.FrozenInstanceError):
        cop_state.position = Coordinate(5, 5)  # type: ignore[misc]


def test_initial_state_reads_only_its_own_start_cell(shared_config):
    """Both start cells sit in the same config; only one is read."""
    cop = LocalState.initial(Role.POLICE, shared_config)
    thief = LocalState.initial(Role.THIEF, shared_config)

    assert cop.position == Coordinate.from_pair(shared_config.board_and_agents.cop_start)
    assert thief.position == Coordinate.from_pair(
        shared_config.board_and_agents.thief_start
    )
    # Neither can see where the other started.
    assert not hasattr(cop, "thief_start")
    assert not hasattr(thief, "cop_start")


# ----------------------------------------------------------------------
# Serialisation
# ----------------------------------------------------------------------


def test_serialisation_contains_no_opponent_position(cop_state, thief_state):
    """Whatever leaves the object cannot contain what the object never had."""
    for state in (cop_state, thief_state):
        payload = state.to_public_dict()
        text = json.dumps(payload)
        for banned in FORBIDDEN_STATE_FIELDS:
            assert banned not in payload
            assert banned not in text


def test_serialised_cop_state_does_not_encode_the_thief_cell(
    cop_state, thief_state
):
    """The thief's actual coordinates must not appear anywhere in the payload."""
    payload = cop_state.to_public_dict()
    values = json.dumps(payload)
    assert payload["position"] == cop_state.position.as_list()
    # The thief starts at [3,3]; that pair must not be present.
    assert thief_state.position.as_list() not in [payload["position"]]
    assert "\"position\": [3, 3]" not in values


def test_serialised_state_exposes_only_legal_keys(cop_state):
    assert set(cop_state.to_public_dict()) == {
        "role",
        "position",
        "turn",
        "barriers_placed",
        "barriers",
        "board_size",
        "finished",
        "terminal",
    }


# ----------------------------------------------------------------------
# The public API surface
# ----------------------------------------------------------------------


def test_no_domain_function_offers_global_truth():
    """No strategy-facing entry point takes or returns both positions."""
    from police_thief.domain import rules

    for name, fn in inspect.getmembers(rules, inspect.isfunction):
        if fn.__module__ != rules.__name__:
            continue
        params = set(inspect.signature(fn).parameters)
        assert not (params & {"opponent", "opponent_cell", "opponent_state"}), (
            f"rules.{name} accepts opponent information"
        )


def test_capture_functions_are_not_methods_on_local_state():
    """Capture needs both positions, so it lives outside the peer's state."""
    for name in ("evaluate_capture", "is_captured", "capture", "check_capture"):
        assert not hasattr(LocalState, name)


def test_barriers_are_public_and_that_is_legitimate(cop_state, thief_state):
    """Not a leak: the cop must declare every placement (E-15, E-16).

    Recorded explicitly so a future reader does not "fix" this by hiding them.
    """
    assert cop_state.board.barriers == thief_state.board.barriers == frozenset()
    assert "barriers" in cop_state.to_public_dict()


# ----------------------------------------------------------------------
# The harness is a separate type, and stays outside the states
# ----------------------------------------------------------------------


def test_harness_is_a_distinct_type_from_local_state(shared_config):
    harness = MatchHarness(shared_config)
    assert not isinstance(harness, LocalState)
    assert type(harness).__name__ == "MatchHarness"
    assert type(harness).__module__.startswith("police_thief.sim")


def test_harness_omniscience_never_enters_either_state(shared_config):
    """The harness holds both positions; neither state does."""
    harness = MatchHarness(shared_config)
    assert harness.cop_cell != harness.thief_cell

    for state in (harness.cop, harness.thief):
        for banned in FORBIDDEN_STATE_FIELDS:
            assert not hasattr(state, banned)

    # The cop's state knows the cop's cell and nothing about the thief's.
    assert harness.cop.position == harness.cop_cell
    assert harness.thief.position == harness.thief_cell
    assert harness.cop.position != harness.thief.position


def test_leak_inspection_over_a_whole_played_sub_game(shared_config):
    """Play to completion, then inspect every state that existed."""
    harness = MatchHarness(shared_config)
    outcome = harness.run(first_legal_move, cycle_directions)

    for state in (outcome.cop_state, outcome.thief_state):
        payload = json.dumps(state.to_public_dict())
        for banned in FORBIDDEN_STATE_FIELDS:
            assert not hasattr(state, banned)
            assert banned not in payload

    # The two peers ended on different cells and neither recorded the other's.
    assert outcome.cop_state.position != outcome.thief_state.position
    assert set(outcome.cop_state.to_public_dict()) == set(
        outcome.thief_state.to_public_dict()
    )


def test_sim_package_is_documented_as_test_only():
    """The omniscient component must not be mistaken for production authority."""
    import police_thief.sim as sim

    doc = (sim.__doc__ or "").lower()
    assert "test-only" in doc or "test only" in doc
    assert "nothing in this package is production authority" in doc
