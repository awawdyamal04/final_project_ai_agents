"""Appendix F policy enforcement and cross-field consistency.

The parametrised policy tests are generated from PARAMETER_POLICIES itself, so
adding a parameter to the table automatically adds its tests. That is the point:
coverage cannot silently fall behind the table.
"""

from __future__ import annotations

import copy

import pytest

from police_thief.config.exceptions import (
    FixedParameterViolationError,
    InvalidConfigValueError,
    InvalidCrossFieldConfigError,
    MinimumParameterViolationError,
)
from police_thief.config.loader import build_shared_config
from police_thief.config.policy import (
    BINDING_PARAMETER_COUNT,
    PARAMETER_POLICIES,
    POLICIES_BY_PATH,
)
from police_thief.config.validation import validate_parameter_policies
from police_thief.domain.enums import ParameterStatus

FIXED_POLICIES = [p for p in PARAMETER_POLICIES if p.status is ParameterStatus.FIXED]
MINIMUM_POLICIES = [
    p for p in PARAMETER_POLICIES if p.status is ParameterStatus.MINIMUM
]
NEGOTIABLE_POLICIES = [
    p for p in PARAMETER_POLICIES if p.status is ParameterStatus.NEGOTIABLE
]


# --------------------------------------------------------------------------
# The table itself
# --------------------------------------------------------------------------


def test_exactly_32_binding_parameters():
    assert len(PARAMETER_POLICIES) == BINDING_PARAMETER_COUNT == 32


def test_each_parameter_appears_exactly_once():
    paths = [p.path for p in PARAMETER_POLICIES]
    assert len(set(paths)) == len(paths) == 32
    code_names = [p.code_name for p in PARAMETER_POLICIES]
    assert len(set(code_names)) == len(code_names) == 32


def test_status_distribution_matches_appendix_f():
    """14 FIXED, 9 MINIMUM, 9 NEGOTIABLE -- counted from the rendered tables."""
    assert len(FIXED_POLICIES) == 14
    assert len(MINIMUM_POLICIES) == 9
    assert len(NEGOTIABLE_POLICIES) == 9
    assert len(FIXED_POLICIES) + len(MINIMUM_POLICIES) + len(NEGOTIABLE_POLICIES) == 32


def test_only_three_statuses_exist():
    """PDF p. 155: exactly three. No DEFAULT, no OPTIONAL."""
    assert {s.value for s in ParameterStatus} == {"fixed", "minimum", "negotiable"}
    assert {p.status for p in PARAMETER_POLICIES} <= set(ParameterStatus)


def test_shipped_config_carries_every_binding_value(valid_shared):
    """The shipped default must be exactly the tabulated value everywhere."""
    for policy in PARAMETER_POLICIES:
        actual = valid_shared[policy.section][policy.key]
        assert actual == policy.binding_value, (
            f"{policy.path}: shipped {actual!r}, tabulated "
            f"{policy.binding_value!r}"
        )


def test_all_32_validate_against_the_shipped_config(valid_shared):
    assert validate_parameter_policies(valid_shared) == 32


# --------------------------------------------------------------------------
# FIXED
# --------------------------------------------------------------------------


@pytest.mark.parametrize("policy", FIXED_POLICIES, ids=lambda p: p.path)
def test_fixed_parameter_accepts_the_binding_value(valid_shared, policy):
    valid_shared[policy.section][policy.key] = copy.deepcopy(policy.binding_value)
    assert validate_parameter_policies(valid_shared) == 32


@pytest.mark.parametrize("policy", FIXED_POLICIES, ids=lambda p: p.path)
def test_fixed_parameter_rejects_a_different_value(valid_shared, policy):
    binding = policy.binding_value
    if isinstance(binding, list):
        altered = binding + ["NE"]
    elif isinstance(binding, bool):
        altered = not binding
    elif isinstance(binding, (int, float)):
        altered = binding + 1
    else:
        altered = f"{binding}-altered"

    valid_shared[policy.section][policy.key] = altered
    with pytest.raises(FixedParameterViolationError, match="FIXED"):
        validate_parameter_policies(valid_shared)


def test_fixed_move_set_rejects_a_reordering():
    """A FIXED list is fixed in order too -- N,S,E,W,STAY is the agreed set."""
    import json

    from tests.conftest import SHARED_CONFIG_PATH

    mapping = json.loads(SHARED_CONFIG_PATH.read_text(encoding="utf-8"))
    mapping["movement_and_barriers"]["move_set"] = ["STAY", "N", "S", "E", "W"]
    with pytest.raises(FixedParameterViolationError):
        validate_parameter_policies(mapping)


def test_fixed_move_set_rejects_a_diagonal(valid_shared):
    valid_shared["movement_and_barriers"]["move_set"] = [
        "N", "S", "E", "W", "NE", "STAY",
    ]
    with pytest.raises(FixedParameterViolationError):
        validate_parameter_policies(valid_shared)


# --------------------------------------------------------------------------
# MINIMUM
# --------------------------------------------------------------------------


@pytest.mark.parametrize("policy", MINIMUM_POLICIES, ids=lambda p: p.path)
def test_minimum_parameter_accepts_the_floor(valid_shared, policy):
    valid_shared[policy.section][policy.key] = policy.binding_value
    assert validate_parameter_policies(valid_shared) == 32


@pytest.mark.parametrize("policy", MINIMUM_POLICIES, ids=lambda p: p.path)
def test_minimum_parameter_accepts_a_greater_value(valid_shared, policy):
    valid_shared[policy.section][policy.key] = policy.binding_value + 1
    # grid_size interacts with cross-field rules; policy layer alone is checked.
    assert validate_parameter_policies(valid_shared) == 32


@pytest.mark.parametrize("policy", MINIMUM_POLICIES, ids=lambda p: p.path)
def test_minimum_parameter_rejects_a_lower_value(valid_shared, policy):
    valid_shared[policy.section][policy.key] = policy.binding_value - 1
    with pytest.raises(MinimumParameterViolationError, match="below the binding"):
        validate_parameter_policies(valid_shared)


def test_grid_size_below_seven_is_rejected(valid_shared):
    """E-12 in its most consequential form: never ease the board below 7x7."""
    valid_shared["board_and_agents"]["grid_size"] = 5
    with pytest.raises(MinimumParameterViolationError):
        validate_parameter_policies(valid_shared)


def test_raised_minimums_survive_full_construction(valid_shared):
    """A harder-but-legal negotiated config must load end to end."""
    valid_shared["board_and_agents"]["grid_size"] = 10
    valid_shared["movement_and_barriers"]["max_moves"] = 50
    valid_shared["movement_and_barriers"]["survival_threshold"] = 45
    valid_shared["movement_and_barriers"]["max_barriers"] = 20
    shared = build_shared_config(valid_shared)
    assert shared.grid_size == 10
    assert shared.movement_and_barriers.survival_threshold == 45


# --------------------------------------------------------------------------
# NEGOTIABLE
# --------------------------------------------------------------------------


@pytest.mark.parametrize("policy", NEGOTIABLE_POLICIES, ids=lambda p: p.path)
def test_negotiable_parameter_accepts_the_tabulated_default(valid_shared, policy):
    valid_shared[policy.section][policy.key] = copy.deepcopy(policy.binding_value)
    assert validate_parameter_policies(valid_shared) == 32


@pytest.mark.parametrize(
    ("section", "key", "agreed"),
    [
        ("board_and_agents", "axis_origin_corner", "bottom-left"),
        ("board_and_agents", "axis_start_index", 1),
        ("board_and_agents", "thief_start", [2, 2]),
        ("board_and_agents", "cop_start", [6, 6]),
        ("world", "map_area", "London"),
        ("world", "map_area", ""),  # empty = generic landmarks
        ("world", "hint_max_words", 20),
        ("network_and_league", "token_budget_per_series", 50000),
        ("network_and_league", "response_timeout_sec", 45),
    ],
)
def test_negotiable_parameter_accepts_an_agreed_value(
    valid_shared, section, key, agreed
):
    valid_shared[section][key] = agreed
    assert validate_parameter_policies(valid_shared) == 32


@pytest.mark.parametrize(
    ("section", "key", "bad"),
    [
        ("board_and_agents", "axis_origin_corner", "middle"),
        ("world", "hint_max_words", 0),
        ("network_and_league", "token_budget_per_series", -1),
        ("network_and_league", "response_timeout_sec", 0),
    ],
)
def test_negotiable_parameter_rejects_an_out_of_domain_value(
    valid_shared, section, key, bad
):
    valid_shared[section][key] = bad
    with pytest.raises(InvalidConfigValueError):
        validate_parameter_policies(valid_shared)


def test_axis_start_index_one_shifts_the_board(valid_shared):
    """A 1-indexed board is negotiable; start cells must move with it."""
    valid_shared["board_and_agents"]["axis_start_index"] = 1
    valid_shared["board_and_agents"]["cop_start"] = [1, 1]
    valid_shared["board_and_agents"]["thief_start"] = [4, 4]
    shared = build_shared_config(valid_shared)
    assert shared.in_bounds((1, 1))
    assert shared.in_bounds((7, 7))
    assert not shared.in_bounds((0, 0))
    assert not shared.in_bounds((8, 8))


# --------------------------------------------------------------------------
# Cross-field
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["thief_start", "cop_start"])
def test_start_cell_outside_the_board_is_rejected(valid_shared, key):
    valid_shared["board_and_agents"][key] = [9, 9]
    with pytest.raises(InvalidCrossFieldConfigError, match="outside"):
        build_shared_config(valid_shared)


def test_negative_start_cell_is_rejected(valid_shared):
    valid_shared["board_and_agents"]["cop_start"] = [-1, 0]
    with pytest.raises(InvalidCrossFieldConfigError, match="outside"):
        build_shared_config(valid_shared)


def test_identical_start_cells_are_rejected(valid_shared):
    """Capture would hold before the first move."""
    valid_shared["board_and_agents"]["thief_start"] = [0, 0]
    with pytest.raises(InvalidCrossFieldConfigError, match="before the"):
        build_shared_config(valid_shared)


def test_survival_threshold_above_max_moves_is_rejected(valid_shared):
    """Survival is a documented win condition; it must be reachable."""
    valid_shared["movement_and_barriers"]["survival_threshold"] = 60
    valid_shared["movement_and_barriers"]["max_moves"] = 40
    with pytest.raises(InvalidCrossFieldConfigError, match="could never survive"):
        build_shared_config(valid_shared)


def test_barrier_quota_beyond_board_capacity_is_rejected(valid_shared):
    valid_shared["movement_and_barriers"]["max_barriers"] = 48
    with pytest.raises(InvalidCrossFieldConfigError, match="exceeds"):
        build_shared_config(valid_shared)


def test_scent_window_wider_than_the_board_is_rejected(valid_shared):
    """Legal only because grid_size may be raised; 5x5 must still fit."""
    valid_shared["board_and_agents"]["grid_size"] = 7
    valid_shared["pheromones"]["pheromone_grid_size"] = 9
    with pytest.raises(
        (InvalidCrossFieldConfigError, FixedParameterViolationError)
    ):
        build_shared_config(valid_shared)


def test_response_timeout_not_shorter_than_watchdog_is_rejected(valid_shared):
    valid_shared["network_and_league"]["response_timeout_sec"] = 90
    valid_shared["network_and_league"]["watchdog_timeout_sec"] = 60
    with pytest.raises(InvalidCrossFieldConfigError, match="shorter"):
        build_shared_config(valid_shared)


def test_shipped_config_passes_every_layer(shared_path):
    from police_thief.config.loader import load_shared_config

    shared = load_shared_config(shared_path)
    assert shared.grid_size == 7
    assert shared.network_and_league.num_games == 6
    assert shared.movement_and_barriers.move_set == ("N", "S", "E", "W", "STAY")


def test_policy_lookup_by_path_is_complete():
    assert len(POLICIES_BY_PATH) == 32
    assert POLICIES_BY_PATH["board_and_agents.grid_size"].status is (
        ParameterStatus.MINIMUM
    )
    assert POLICIES_BY_PATH["network_and_league.num_games"].binding_value == 6
