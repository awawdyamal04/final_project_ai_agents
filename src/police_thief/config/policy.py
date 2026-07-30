"""The Appendix F mandatory parameter table, as data.

**This module is the only place in the codebase where an Appendix F numeric
value may appear.** Everything else reads a loaded config object. Scattering
these literals through game logic would make E-11 (byte-identical config) and
E-12 (never lower a minimum) unenforceable, because there would be no single
thing to check against.

Source: ``police_thief.pdf`` Appendix F, PDF pp. 152-155, verified against the
rendered pages rather than a text extraction (the book is right-to-left and text
extraction returns table cells out of order). See docs/PARAMETERS.md.

The "example value" column is binding
-------------------------------------
PDF p. 151: "the values presented in the 'example value' column **are the
binding minimum**: it is permitted to raise them by mutual agreement between the
two playing teams, but it is forbidden to lower them below this bar."

So the column heading says *example* while its contents are mandatory. Under all
three statuses the tabulated value is the code's default, which is why
``binding_value`` below is used both as the shipped default and as the bar that
validation enforces.

Statuses (PDF p. 155 -- exactly three, no DEFAULT, no OPTIONAL)
---------------------------------------------------------------
FIXED       must equal the binding value exactly; deviation disqualifies
MINIMUM     must not be below the binding value
NEGOTIABLE  any agreed value, correctly typed and internally valid
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from police_thief.domain.enums import ParameterStatus

FIXED = ParameterStatus.FIXED
MINIMUM = ParameterStatus.MINIMUM
NEGOTIABLE = ParameterStatus.NEGOTIABLE


@dataclass(frozen=True, slots=True)
class ParameterPolicy:
    """One row of the Appendix F mandatory parameter table."""

    code_name: str
    """The PDF's bracketed Hebrew code-name, e.g. ``[grid_size]``."""

    section: str
    """Top-level object in ``config/game.json``, e.g. ``board_and_agents``."""

    key: str
    """Key within that section."""

    status: ParameterStatus
    binding_value: Any
    """The tabulated value: the FIXED value, the MINIMUM floor, or the
    NEGOTIABLE default."""

    py_type: type | tuple[type, ...]
    unit: str | None
    pdf_table: int
    pdf_page: int
    meaning: str

    @property
    def path(self) -> str:
        return f"{self.section}.{self.key}"


# --------------------------------------------------------------------------
# The 32 binding parameters.
# --------------------------------------------------------------------------

PARAMETER_POLICIES: tuple[ParameterPolicy, ...] = (
    # -- Table 13: board, axis system, start positions (PDF p. 152) ---------
    ParameterPolicy(
        "[grid_size]", "board_and_agents", "grid_size",
        MINIMUM, 7, int, "cells (side)", 13, 152,
        "Side of the square game grid",
    ),
    ParameterPolicy(
        "[num_agents]", "board_and_agents", "num_agents",
        FIXED, 2, int, None, 13, 152,
        "Number of players in the race",
    ),
    ParameterPolicy(
        "[axis_origin_corner]", "board_and_agents", "axis_origin_corner",
        NEGOTIABLE, "top-left", str, None, 13, 152,
        "The corner in which cell (0,0) sits",
    ),
    ParameterPolicy(
        "[axis_start_index]", "board_and_agents", "axis_start_index",
        NEGOTIABLE, 0, int, None, 13, 152,
        "The number at which each axis starts counting",
    ),
    ParameterPolicy(
        "[thief_start]", "board_and_agents", "thief_start",
        NEGOTIABLE, [3, 3], list, "(row, col)", 13, 152,
        "The thief's start cell",
    ),
    ParameterPolicy(
        "[cop_start]", "board_and_agents", "cop_start",
        NEGOTIABLE, [0, 0], list, "(row, col)", 13, 152,
        "The cop's start cell",
    ),
    # -- Table 14: arena and verbal hints (PDF p. 152) ----------------------
    ParameterPolicy(
        "[map_area]", "world", "map_area",
        NEGOTIABLE, "New York", str, None, 14, 152,
        "Real-world region feeding landmarks into hints; empty = generic",
    ),
    ParameterPolicy(
        "[hint_max_words]", "world", "hint_max_words",
        NEGOTIABLE, 15, int, "words", 14, 152,
        "Maximum words in each verbal hint, template and LLM alike",
    ),
    # -- Table 15: movement and barriers (PDF p. 153) -----------------------
    ParameterPolicy(
        "[move_set]", "movement_and_barriers", "move_set",
        FIXED, ["N", "S", "E", "W", "STAY"], list, None, 15, 153,
        "One orthogonal move or standing still; no diagonals",
    ),
    ParameterPolicy(
        "[max_barriers]", "movement_and_barriers", "max_barriers",
        MINIMUM, 14, int, None, 15, 153,
        "Maximum barriers the cop may place",
    ),
    ParameterPolicy(
        "[max_moves]", "movement_and_barriers", "max_moves",
        MINIMUM, 35, int, "moves", 15, 153,
        "Maximum moves in a sub-game",
    ),
    ParameterPolicy(
        "[survival_threshold]", "movement_and_barriers", "survival_threshold",
        MINIMUM, 35, int, "steps", 15, 153,
        "Steps the thief must survive to win",
    ),
    # -- Table 16: dynamic pheromones (PDF p. 153) --------------------------
    ParameterPolicy(
        "[pheromone_center_intensity]", "pheromones",
        "pheromone_center_intensity",
        FIXED, 0.9, float, None, 16, 153,
        "Pheromone intensity in the emitting cell",
    ),
    ParameterPolicy(
        "[pheromone_decay]", "pheromones", "pheromone_decay",
        FIXED, 0.10, float, "per turn", 16, 153,
        "Decay rate per turn (rho)",
    ),
    ParameterPolicy(
        "[pheromone_grid_size]", "pheromones", "pheromone_grid_size",
        FIXED, 5, int, "cells (side)", 16, 153,
        "Side of the emission window around the agent",
    ),
    # -- Table 17: scoring (PDF p. 154) -------------------------------------
    ParameterPolicy(
        "[capture_cop]", "scoring", "capture_cop",
        FIXED, 20, int, "points", 17, 154,
        "Score to the cop on a successful capture",
    ),
    ParameterPolicy(
        "[capture_thief]", "scoring", "capture_thief",
        FIXED, 5, int, "points", 17, 154,
        "Score to the thief on a capture",
    ),
    ParameterPolicy(
        "[survival_cop]", "scoring", "survival_cop",
        FIXED, 5, int, "points", 17, 154,
        "Score to the cop when the thief survives",
    ),
    ParameterPolicy(
        "[survival_thief]", "scoring", "survival_thief",
        FIXED, 10, int, "points", 17, 154,
        "Score to the thief on successful survival",
    ),
    ParameterPolicy(
        "[tie_score]", "scoring", "tie_score",
        FIXED, 2, int, "points", 17, 154,
        "Score to each side when cumulative totals tie across all sub-games",
    ),
    # -- Table 18: network and league (PDF p. 154) --------------------------
    ParameterPolicy(
        "[num_sub_games]", "network_and_league", "num_games",
        FIXED, 6, int, "sub-games", 18, 154,
        "Sub-games in a series against one opponent",
    ),
    ParameterPolicy(
        "[diversity_reward]", "network_and_league", "diversity_reward",
        FIXED, 10, int, "points", 18, 154,
        "Score for a victory against a new opponent",
    ),
    ParameterPolicy(
        "[min_games_to_pass]", "network_and_league", "min_games_to_pass",
        FIXED, 2, int, "matches", 18, 154,
        "Minimum matches per team for a passing grade",
    ),
    ParameterPolicy(
        "[token_budget_per_series]", "network_and_league",
        "token_budget_per_series",
        NEGOTIABLE, 200000, int, "tokens", 18, 154,
        "Total LLM tokens each team may consume; actual use is reported",
    ),
    ParameterPolicy(
        "[max_games_per_team]", "network_and_league", "max_games_per_team",
        FIXED, 10, int, "matches", 18, 154,
        "Maximum matches each team may play",
    ),
    # -- Table 19: rate limiter, gatekeeper, timeouts (PDF p. 155) ----------
    ParameterPolicy(
        "[requests_per_minute]", "rate_limiter_gatekeeper",
        "requests_per_minute",
        MINIMUM, 30, int, "requests/minute", 19, 155,
        "Maximum rate of outgoing API requests",
    ),
    ParameterPolicy(
        "[concurrent_requests]", "rate_limiter_gatekeeper",
        "concurrent_requests",
        MINIMUM, 2, int, None, 19, 155,
        "Maximum concurrent requests",
    ),
    ParameterPolicy(
        "[retry_backoff_sec]", "rate_limiter_gatekeeper", "retry_backoff_sec",
        MINIMUM, 5, int, "seconds", 19, 155,
        "Wait before a retry",
    ),
    ParameterPolicy(
        "[max_retries]", "rate_limiter_gatekeeper", "max_retries",
        MINIMUM, 3, int, None, 19, 155,
        "Attempts before failure",
    ),
    ParameterPolicy(
        "[queue_depth]", "rate_limiter_gatekeeper", "queue_depth",
        MINIMUM, 100, int, None, 19, 155,
        "Request-queue size under load",
    ),
    ParameterPolicy(
        "[response_timeout_sec]", "network_and_league", "response_timeout_sec",
        NEGOTIABLE, 30, int, "seconds", 19, 155,
        "Timeout for each network request",
    ),
    ParameterPolicy(
        "[watchdog_timeout_sec]", "network_and_league", "watchdog_timeout_sec",
        NEGOTIABLE, 60, int, "seconds", 19, 155,
        "Freeze time until watchdog intervention",
    ),
)


BINDING_PARAMETER_COUNT = 32
"""Appendix F tabulates exactly 32 binding parameters across tables 13-19."""


POLICIES_BY_PATH: dict[str, ParameterPolicy] = {
    policy.path: policy for policy in PARAMETER_POLICIES
}


def policies_for_section(section: str) -> tuple[ParameterPolicy, ...]:
    return tuple(p for p in PARAMETER_POLICIES if p.section == section)


def policies_with_status(status: ParameterStatus) -> tuple[ParameterPolicy, ...]:
    return tuple(p for p in PARAMETER_POLICIES if p.status is status)


# --------------------------------------------------------------------------
# Non-Appendix-F keys that are nonetheless part of the shared document.
# --------------------------------------------------------------------------

STRUCTURAL_SHARED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "schema_version": str,
    "agreed_between": list,
}
"""Structural fields of ``config/game.json`` from Appendix B (PDF p. 129).

Not Appendix F parameters and carrying no MINIMUM/FIXED/NEGOTIABLE status, but
part of the shared document and therefore part of ``config_sha256``.
"""

TECHNICAL_LOSS_DEFAULT = 0
"""``scoring.technical_loss``: present in the Appendix B example (PDF p. 129),
Ch. 3's scoring table (PDF p. 38) and rule E-48 (PDF p. 149) -- but **absent
from Appendix F table 17**, so it carries no binding status. Treated as
negotiable-with-default-0. See DECISIONS.md D-3.
"""


def _self_check() -> None:
    """Guard the invariants this module exists to provide.

    Runs at import so a typo in the table above fails loudly at start-up rather
    than silently weakening validation.
    """
    if len(PARAMETER_POLICIES) != BINDING_PARAMETER_COUNT:
        raise AssertionError(
            f"expected {BINDING_PARAMETER_COUNT} Appendix F parameters, "
            f"found {len(PARAMETER_POLICIES)}"
        )
    paths = [p.path for p in PARAMETER_POLICIES]
    if len(set(paths)) != len(paths):
        duplicates = sorted({p for p in paths if paths.count(p) > 1})
        raise AssertionError(f"duplicate parameter paths: {duplicates}")
    code_names = [p.code_name for p in PARAMETER_POLICIES]
    if len(set(code_names)) != len(code_names):
        duplicates = sorted({c for c in code_names if code_names.count(c) > 1})
        raise AssertionError(f"duplicate code-names: {duplicates}")


_self_check()
