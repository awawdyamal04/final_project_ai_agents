"""Validation of shared and private configuration.

Three layers, applied in order, each with its own exception type so a test can
assert *which* rule was broken:

1. **Closed schema.** Unknown, renamed or missing keys are rejected; types and
   shapes are checked. Field names are fixed and binding (PDF p. 130):
   negotiation changes what a value *is*, never what a key is *called*.
2. **Appendix F policy.** FIXED must match exactly; MINIMUM must not be lower;
   NEGOTIABLE must be present and well-typed (E-12).
3. **Cross-field.** Individually valid values that contradict one another.

Layer 3 is the only place containing rules the PDF does not state verbatim.
Every such rule is marked ``DERIVED`` with the reasoning that supports it, so a
later reader can tell what was quoted from what was inferred.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from police_thief.config.exceptions import (
    FixedParameterViolationError,
    InvalidConfigTypeError,
    InvalidConfigValueError,
    InvalidCrossFieldConfigError,
    MinimumParameterViolationError,
    MissingConfigFieldError,
    PrivateConfigShadowsSharedError,
    UnknownConfigFieldError,
)
from police_thief.config.policy import (
    PARAMETER_POLICIES,
    STRUCTURAL_SHARED_FIELDS,
    ParameterPolicy,
    policies_for_section,
)
from police_thief.domain.enums import AxisOriginCorner, ParameterStatus, Role

# --------------------------------------------------------------------------
# Layer 1: closed schema
# --------------------------------------------------------------------------

SHARED_SECTIONS: tuple[str, ...] = (
    "board_and_agents",
    "world",
    "movement_and_barriers",
    "scoring",
    "pheromones",
    "network_and_league",
    "rate_limiter_gatekeeper",
)

_EXTRA_SECTION_KEYS: dict[str, dict[str, type | tuple[type, ...]]] = {
    # Present in the Appendix B example and Ch. 3's scoring table, but absent
    # from Appendix F table 17 -- so it is part of the schema without carrying a
    # binding status. See DECISIONS.md D-3.
    "scoring": {"technical_loss": int},
}


def _expected_keys(section: str) -> dict[str, type | tuple[type, ...]]:
    expected: dict[str, type | tuple[type, ...]] = {
        policy.key: policy.py_type for policy in policies_for_section(section)
    }
    expected.update(_EXTRA_SECTION_KEYS.get(section, {}))
    return expected


def validate_shared_schema(mapping: Mapping[str, Any]) -> None:
    """Check the shared document against the closed schema."""
    if not isinstance(mapping, dict):
        raise InvalidConfigTypeError(
            f"shared configuration must be a JSON object, got "
            f"{type(mapping).__name__}"
        )

    allowed_top = set(STRUCTURAL_SHARED_FIELDS) | set(SHARED_SECTIONS)
    present_top = set(mapping)

    for unknown in sorted(present_top - allowed_top):
        raise UnknownConfigFieldError(
            f"unknown top-level field {unknown!r}. Field names are fixed and "
            f"binding (PDF p. 130); allowed: {sorted(allowed_top)}"
        )
    for missing in sorted(allowed_top - present_top):
        raise MissingConfigFieldError(
            f"missing top-level field {missing!r} (Appendix F section 2, "
            f"PDF p. 156: every team must define all values)"
        )

    for name, expected_type in STRUCTURAL_SHARED_FIELDS.items():
        _check_type(mapping[name], expected_type, name)

    for section in SHARED_SECTIONS:
        body = mapping[section]
        if not isinstance(body, dict):
            raise InvalidConfigTypeError(
                f"{section} must be an object, got {type(body).__name__}"
            )
        expected = _expected_keys(section)
        for unknown in sorted(set(body) - set(expected)):
            raise UnknownConfigFieldError(
                f"unknown field {section}.{unknown!r}. Field names are fixed "
                f"and binding (PDF p. 130); allowed in {section}: "
                f"{sorted(expected)}"
            )
        for missing in sorted(set(expected) - set(body)):
            raise MissingConfigFieldError(f"missing field {section}.{missing}")
        for key, expected_type in expected.items():
            _check_type(body[key], expected_type, f"{section}.{key}")


def _check_type(
    value: Any, expected: type | tuple[type, ...], path: str
) -> None:
    # bool is a subclass of int; a JSON `true` where an int belongs is a real
    # error, not an int worth 1.
    if isinstance(value, bool) and expected is not bool:
        raise InvalidConfigTypeError(
            f"{path}: expected {_type_name(expected)}, got bool"
        )
    if expected is float and isinstance(value, int):
        return  # JSON writes 1 for 1.0; accept the widening.
    if not isinstance(value, expected):
        raise InvalidConfigTypeError(
            f"{path}: expected {_type_name(expected)}, "
            f"got {type(value).__name__}"
        )


def _type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(t.__name__ for t in expected)
    return expected.__name__


# --------------------------------------------------------------------------
# Layer 2: Appendix F policy
# --------------------------------------------------------------------------


def validate_parameter_policies(mapping: Mapping[str, Any]) -> int:
    """Enforce FIXED / MINIMUM / NEGOTIABLE. Returns the number checked."""
    for policy in PARAMETER_POLICIES:
        value = mapping[policy.section][policy.key]
        _validate_one_policy(policy, value)
    return len(PARAMETER_POLICIES)


def _values_equal(actual: Any, binding: Any) -> bool:
    """Compare a loaded value against a FIXED binding value.

    Lists compare element-wise and order-sensitively: ``move_set`` is fixed as
    a sequence, and a reordering is a different agreement.

    Floats compare with a tolerance. ``0.10`` in the file and ``0.10`` in the
    policy table parse to the same double today, but binary floating point makes
    that a property of these particular literals rather than a guarantee, and a
    FIXED parameter should not fail on a last-bit difference.
    """
    if isinstance(actual, bool) != isinstance(binding, bool):
        return False
    if isinstance(binding, list):
        if not isinstance(actual, list) or len(actual) != len(binding):
            return False
        return all(_values_equal(a, b) for a, b in zip(actual, binding, strict=True))
    if isinstance(binding, float) or isinstance(actual, float):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            return False
        return math.isclose(float(actual), float(binding), rel_tol=1e-9, abs_tol=1e-12)
    return actual == binding


def _validate_one_policy(policy: ParameterPolicy, value: Any) -> None:
    if policy.status is ParameterStatus.FIXED:
        if not _values_equal(value, policy.binding_value):
            raise FixedParameterViolationError(
                f"{policy.path}: FIXED at {policy.binding_value!r} "
                f"(Appendix F table {policy.pdf_table}, PDF p. {policy.pdf_page}), "
                f"got {value!r}. Deviating from a fixed value disqualifies the "
                f"team (PDF p. 155)."
            )
        return

    if policy.status is ParameterStatus.MINIMUM:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise InvalidConfigTypeError(
                f"{policy.path}: MINIMUM parameter must be numeric, "
                f"got {type(value).__name__}"
            )
        if value < policy.binding_value:
            raise MinimumParameterViolationError(
                f"{policy.path}: below the binding minimum "
                f"{policy.binding_value!r} (Appendix F table {policy.pdf_table}, "
                f"PDF p. {policy.pdf_page}), got {value!r}. Minimums may be "
                f"raised by mutual agreement but never lowered (E-12)."
            )
        return

    # NEGOTIABLE: presence and type are guaranteed by layer 1. Domain checks
    # that apply regardless of agreement live here.
    _validate_negotiable_domain(policy, value)


def _validate_negotiable_domain(policy: ParameterPolicy, value: Any) -> None:
    if policy.key == "axis_origin_corner":
        valid = {c.value for c in AxisOriginCorner}
        if value not in valid:
            raise InvalidConfigValueError(
                f"{policy.path}: must be one of {sorted(valid)}, got {value!r}"
            )
    elif policy.key in ("thief_start", "cop_start"):
        _validate_coord(value, policy.path)
    elif policy.key == "hint_max_words":
        if value < 1:
            raise InvalidConfigValueError(
                f"{policy.path}: must be at least 1 word, got {value!r}"
            )
    elif policy.key == "token_budget_per_series":
        if value < 0:
            raise InvalidConfigValueError(
                f"{policy.path}: must not be negative, got {value!r}"
            )
    elif policy.key in ("response_timeout_sec", "watchdog_timeout_sec"):
        if value < 1:
            raise InvalidConfigValueError(
                f"{policy.path}: must be at least 1 second, got {value!r}"
            )


def _validate_coord(value: Any, path: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise InvalidConfigTypeError(
            f"{path}: expected a [row, col] pair, got {value!r}"
        )
    for index, component in enumerate(value):
        if isinstance(component, bool) or not isinstance(component, int):
            raise InvalidConfigTypeError(
                f"{path}[{index}]: coordinates must be integers, "
                f"got {type(component).__name__}"
            )


# --------------------------------------------------------------------------
# Layer 3: cross-field
# --------------------------------------------------------------------------


def validate_cross_fields(mapping: Mapping[str, Any]) -> None:
    """Reject individually valid values that contradict one another.

    Rules marked DERIVED are not stated verbatim in the PDF. Each is a
    consistency guard whose violation would make some documented rule
    unsatisfiable, and the reasoning is given inline.
    """
    board = mapping["board_and_agents"]
    movement = mapping["movement_and_barriers"]
    pheromones = mapping["pheromones"]
    league = mapping["network_and_league"]

    grid = board["grid_size"]
    low = board["axis_start_index"]
    high = low + grid

    # Start cells on the board. PDF p. 34 requires both sides to hold identical
    # axis parameters; a start cell off the board is meaningless under any.
    for key in ("thief_start", "cop_start"):
        row, col = board[key]
        if not (low <= row < high and low <= col < high):
            raise InvalidCrossFieldConfigError(
                f"board_and_agents.{key} = [{row}, {col}] is outside the "
                f"{grid}x{grid} board indexed [{low}, {high - 1}]"
            )

    # DERIVED: distinct start cells. Capture is defined as the cop landing on
    # the thief's cell (Ch. 3, PDF p. 38). Identical start cells would satisfy
    # the capture condition before the first move, making the sub-game
    # degenerate. The PDF permits "any legal agreed layout" (p. 35) but a layout
    # that ends the game at step zero is not a race.
    if list(board["thief_start"]) == list(board["cop_start"]):
        raise InvalidCrossFieldConfigError(
            f"board_and_agents.thief_start and cop_start are both "
            f"{board['cop_start']}; the capture condition would hold before the "
            f"first move"
        )

    # num_agents is FIXED at 2 and exactly two start cells are defined.
    if board["num_agents"] != 2:
        raise InvalidCrossFieldConfigError(
            f"board_and_agents.num_agents = {board['num_agents']} but the "
            f"configuration defines exactly two start positions"
        )

    # DERIVED: the thief must be able to reach the survival threshold within the
    # move ceiling. survival_threshold > max_moves makes survival -- a
    # documented win condition (Ch. 3 scoring table) -- unreachable.
    if movement["survival_threshold"] > movement["max_moves"]:
        raise InvalidCrossFieldConfigError(
            f"movement_and_barriers.survival_threshold "
            f"({movement['survival_threshold']}) exceeds max_moves "
            f"({movement['max_moves']}); the thief could never survive to win"
        )

    # DERIVED: barriers must fit. Both start cells must remain free, so the
    # ceiling is cells - 2. Exceeding it makes the quota unusable.
    capacity = grid * grid - 2
    if movement["max_barriers"] > capacity:
        raise InvalidCrossFieldConfigError(
            f"movement_and_barriers.max_barriers "
            f"({movement['max_barriers']}) exceeds the {capacity} cells "
            f"available on a {grid}x{grid} board once both start cells are "
            f"excluded"
        )

    # DERIVED: the emission window must fit on the board. Ch. 4 (PDF p. 43)
    # describes a window of side pheromone_grid_size centred on the agent; a
    # window wider than the board has no coherent meaning.
    if pheromones["pheromone_grid_size"] > grid:
        raise InvalidCrossFieldConfigError(
            f"pheromones.pheromone_grid_size "
            f"({pheromones['pheromone_grid_size']}) exceeds grid_size ({grid})"
        )

    # Intensity and decay are FIXED, so these only fire if the policy table is
    # ever edited. Cheap insurance on a value the physics depends on.
    if not 0.0 < pheromones["pheromone_center_intensity"] <= 1.0:
        raise InvalidCrossFieldConfigError(
            "pheromones.pheromone_center_intensity must lie in (0, 1]"
        )
    if not 0.0 < pheromones["pheromone_decay"] <= 1.0:
        raise InvalidCrossFieldConfigError(
            "pheromones.pheromone_decay must lie in (0, 1]"
        )

    # DERIVED: a request deadline must be shorter than the process-freeze
    # threshold. Ch. 8 (PDF p. 81) separates the deadline tracker, which guards
    # one request, from the watchdog, which guards the whole process. If the
    # request deadline were the longer of the two the watchdog would fire first
    # and the distinction would collapse.
    if league["response_timeout_sec"] >= league["watchdog_timeout_sec"]:
        raise InvalidCrossFieldConfigError(
            f"network_and_league.response_timeout_sec "
            f"({league['response_timeout_sec']}) must be shorter than "
            f"watchdog_timeout_sec ({league['watchdog_timeout_sec']}); "
            f"otherwise the watchdog fires before a request can time out"
        )

    # DERIVED: the pass threshold must be reachable within the cap. Both are
    # FIXED (2 and 10), so this guards the policy table rather than user input.
    if league["min_games_to_pass"] > league["max_games_per_team"]:
        raise InvalidCrossFieldConfigError(
            f"network_and_league.min_games_to_pass "
            f"({league['min_games_to_pass']}) exceeds max_games_per_team "
            f"({league['max_games_per_team']})"
        )


# --------------------------------------------------------------------------
# Cross-file: the private config must not shadow the shared one
# --------------------------------------------------------------------------

_SHARED_PARAMETER_KEYS: frozenset[str] = frozenset(
    policy.key for policy in PARAMETER_POLICIES
)


def validate_private_does_not_shadow_shared(
    private_mapping: Mapping[str, Any]
) -> None:
    """Reject a private TOML that defines any shared parameter key.

    PDF p. 132 requires the shared JSON to override any parallel key in the
    private TOML, "so the private file can never 'weaken' a signed condition".
    We reject the shadowing outright instead of resolving it. That is strictly
    stronger than overriding -- a key that is never accepted can never win --
    and it lets the two configurations stay separate typed objects rather than
    being merged. See DECISIONS.md D-21.
    """
    for section, body in private_mapping.items():
        if not isinstance(body, dict):
            continue
        for key in body:
            if key in _SHARED_PARAMETER_KEYS:
                raise PrivateConfigShadowsSharedError(
                    f"private configuration defines [{section}] {key!r}, which "
                    f"is owned by the shared constitution. Values the opponent "
                    f"must agree on belong in config/game.json (PDF p. 128); "
                    f"the private file may never weaken a signed condition "
                    f"(PDF p. 132)."
                )


def validate_role_matches(private_role: Role, expected: Role) -> None:
    """Check the private config's role against the launched entry point."""
    if private_role is not expected:
        raise InvalidCrossFieldConfigError(
            f"private configuration declares role {private_role.value!r} but "
            f"the peer was started as {expected.value!r}. The cop and thief run "
            f"as two entirely separate processes under separate configuration "
            f"directories (E-1)."
        )
