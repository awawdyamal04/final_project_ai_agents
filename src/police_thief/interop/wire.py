"""Reference-v3 wire shapes (SPEC section 7.5) as plain dict schemas.

No dataclasses: the kit's own ``sparring/proto/messages.py`` is a dataclass
wrapper around exactly these keys, and this project's one rule for the wire
is "canonical JSON in, canonical JSON out" (``config/canonical.py``), so a
dict is the more honest representation here.
"""

from __future__ import annotations

from typing import Any

from police_thief.config.models import SharedConfig

TURN_REQUIRED: frozenset[str] = frozenset(
    {"step", "sender", "hint", "smell_grid", "commit", "timestamp"}
)
TURN_OPTIONAL: frozenset[str] = frozenset(
    {"barrier_placed", "capture_claim", "claim_response", "win_claim"}
)
CONTROL_REQUIRED: frozenset[str] = frozenset({"kind", "sender"})
CONTROL_OPTIONAL: frozenset[str] = frozenset(
    {"sub_game_number", "status", "step_budget", "payload"}
)
AUDIT_REQUIRED: frozenset[str] = frozenset({"sender", "records", "result_claim"})

#: The kit's flat 14-key TERMS_KEYS (``sparring/config.py``), resolved
#: against this project's real ``config/game.json`` fields. Was left
#: deliberately unresolved in ``protocol/interop_ids.py``'s docstring and
#: docs/OPEN_QUESTIONS.md Q-21 point 3 -- now answered by reading the kit's
#: own ``TERMS_KEYS``/``SparConfig.terms()``. ``min_center_intensity`` has no
#: counterpart in this project's config at all (our scent model has no lower
#: floor -- see ``domain/scent.py``), so it is an adapter-only constant, per
#: the kit's own default (``sparring/rules/scent.py``).
DEFAULT_MIN_CENTER_INTENSITY = 0.5


def terms_from_config(config: SharedConfig) -> dict[str, Any]:
    """The flat, closed 14-key ``terms`` set the reference-v3 negotiate
    signature is computed over (SPEC section 4)."""
    board = config.board_and_agents
    move = config.movement_and_barriers
    return {
        "board_size": board.grid_size,
        "smell_grid_size": config.pheromones.pheromone_grid_size,
        "decay_per_step": config.pheromones.pheromone_decay,
        "emit_intensity": config.pheromones.pheromone_center_intensity,
        "min_center_intensity": DEFAULT_MIN_CENTER_INTENSITY,
        "max_steps": move.max_moves,
        "barriers_max": move.max_barriers,
        "setting": config.world.map_area,
        "hint_max_words": config.world.hint_max_words,
        "axis_origin_corner": board.axis_origin_corner.value,
        "axis_start_index": board.axis_start_index,
        "thief_start": list(board.thief_start),
        "cop_start": list(board.cop_start),
        "num_games": config.network_and_league.num_games,
    }


def turn_message(
    *,
    step: int,
    sender: str,
    hint: str,
    smell_grid: dict[str, float],
    commit: str,
    timestamp: str,
    barrier_placed: list[int] | None = None,
    capture_claim: list[int] | None = None,
    claim_response: dict[str, Any] | None = None,
    win_claim: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one outbound half-turn, the full ten-key set, nulls explicit --
    matching ``turn_message.json``'s own "accept" shape."""
    return {
        "step": step,
        "sender": sender,
        "hint": hint,
        "smell_grid": smell_grid,
        "commit": commit,
        "timestamp": timestamp,
        "barrier_placed": barrier_placed,
        "capture_claim": capture_claim,
        "claim_response": claim_response,
        "win_claim": win_claim,
    }


def control_message(
    *,
    kind: str,
    sender: str,
    sub_game_number: int = 1,
    status: str = "",
    step_budget: float = 0.0,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "sender": sender,
        "sub_game_number": sub_game_number,
        "status": status,
        "step_budget": step_budget,
        "payload": payload,
    }


def audit_payload(
    *, sender: str, records: list[dict[str, Any]], result_claim: str
) -> dict[str, Any]:
    return {"sender": sender, "records": records, "result_claim": result_claim}
