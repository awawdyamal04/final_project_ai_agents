"""Wire representation of a domain action.

Defined now, **transmitted from Phase 5 onward**. A move sent in the clear
before commit-reveal exists would let either side react to the other's choice
within the same turn, which is precisely what the commitment scheme prevents
(Ch. 5, PDF p. 49). Phase 2 therefore has this codec and no message type that
carries its output.

The PDF prescribes no key spelling for actions. This encoding is a project
decision (DECISIONS.md D-30) and must be agreed with the opponent, because
canonical serialisation makes key spelling load-bearing: ``"place_barrier"``
and ``"placeBarrier"`` hash differently, and a disagreement surfaces as a
failed audit rather than a parse error.

Kept separate from both transport and game rules: it imports the domain action
types and nothing else.
"""

from __future__ import annotations

from typing import Any, Mapping

from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ActionKind, Direction
from police_thief.protocol.exceptions import ProtocolValidationError

ACTION_WIRE_VERSION = 1
"""Versioned independently of the envelope: the action encoding may need to
change without changing the conversation around it."""

_ACTION_KEYS: dict[str, frozenset[str]] = {
    ActionKind.MOVE.value: frozenset({"v", "kind", "direction"}),
    ActionKind.PLACE_BARRIER.value: frozenset({"v", "kind", "cell"}),
}


def encode_action(action: Action) -> dict[str, Any]:
    """Encode a domain action into its wire mapping.

    Role-independent: nothing in the output says who acted. The envelope
    carries ``sender_role``, so repeating it here would be a second source of
    truth for the same fact.
    """
    if isinstance(action, Move):
        return {
            "v": ACTION_WIRE_VERSION,
            "kind": ActionKind.MOVE.value,
            "direction": action.direction.value,
        }
    if isinstance(action, PlaceBarrier):
        return {
            "v": ACTION_WIRE_VERSION,
            "kind": ActionKind.PLACE_BARRIER.value,
            "cell": action.cell.as_list(),
        }
    raise ProtocolValidationError(
        f"cannot encode action of type {type(action).__name__}"
    )


def decode_action(raw: Mapping[str, Any]) -> Action:
    """Decode a wire mapping into a domain action.

    Closed schema per kind. Rejects unknown kinds, unknown keys, missing keys
    and malformed coordinates. Board bounds and barrier legality are **not**
    checked here -- that is the domain's job, and it needs a board to do it.
    This codec's contract is only that the result is a well-formed action.
    """
    if not isinstance(raw, dict):
        raise ProtocolValidationError(
            f"action must be an object, got {type(raw).__name__}"
        )

    if raw.get("v") != ACTION_WIRE_VERSION:
        raise ProtocolValidationError(
            f"unsupported action wire version {raw.get('v')!r}; "
            f"this peer speaks {ACTION_WIRE_VERSION}"
        )

    kind = raw.get("kind")
    if kind not in _ACTION_KEYS:
        raise ProtocolValidationError(
            f"unknown action kind {kind!r}; expected one of "
            f"{sorted(_ACTION_KEYS)}"
        )

    allowed = _ACTION_KEYS[kind]
    for unknown in sorted(set(raw) - allowed):
        raise ProtocolValidationError(
            f"{kind}: unknown action field {unknown!r}; allowed: {sorted(allowed)}"
        )
    for missing in sorted(allowed - set(raw)):
        raise ProtocolValidationError(f"{kind}: missing action field {missing!r}")

    if kind == ActionKind.MOVE.value:
        try:
            direction = Direction(raw["direction"])
        except ValueError as exc:
            raise ProtocolValidationError(
                f"unknown direction {raw['direction']!r}; expected one of "
                f"{sorted(d.value for d in Direction)}"
            ) from exc
        return Move(direction)

    return PlaceBarrier(_decode_cell(raw["cell"]))


def _decode_cell(raw: Any) -> Coordinate:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ProtocolValidationError(
            f"cell must be a [row, col] pair, got {raw!r}"
        )
    for component in raw:
        if isinstance(component, bool) or not isinstance(component, int):
            raise ProtocolValidationError(
                f"cell components must be integers, got {raw!r}"
            )
    return Coordinate(raw[0], raw[1])
