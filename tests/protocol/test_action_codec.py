"""Action wire codec.

Defined in Phase 2, transmitted from Phase 5. A move sent before commit-reveal
exists would let either side react within the same turn -- exactly what the
commitment scheme prevents.
"""

from __future__ import annotations

import pytest

from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction
from police_thief.protocol.action_codec import (
    ACTION_WIRE_VERSION,
    decode_action,
    encode_action,
)
from police_thief.protocol.exceptions import ProtocolValidationError


@pytest.mark.parametrize("direction", list(Direction))
def test_move_round_trips_including_stay(direction):
    action = Move(direction)
    assert decode_action(encode_action(action)) == action


def test_place_barrier_round_trips():
    action = PlaceBarrier(Coordinate(3, 4))
    assert decode_action(encode_action(action)) == action


def test_encoding_is_deterministic():
    action = PlaceBarrier(Coordinate(1, 2))
    assert encode_action(action) == encode_action(action)


def test_encoding_is_versioned():
    assert encode_action(Move(Direction.N))["v"] == ACTION_WIRE_VERSION


def test_encoding_is_role_independent():
    """The envelope carries sender_role; repeating it here would be a second
    source of truth for the same fact."""
    wire = encode_action(Move(Direction.N))
    assert "role" not in wire
    assert "sender" not in wire
    assert set(wire) == {"v", "kind", "direction"}


def test_unsupported_version_is_rejected():
    wire = encode_action(Move(Direction.N))
    wire["v"] = 99
    with pytest.raises(ProtocolValidationError, match="unsupported action wire"):
        decode_action(wire)


def test_unknown_kind_is_rejected():
    with pytest.raises(ProtocolValidationError, match="unknown action kind"):
        decode_action({"v": 1, "kind": "teleport", "direction": "N"})


def test_unknown_direction_is_rejected():
    with pytest.raises(ProtocolValidationError, match="unknown direction"):
        decode_action({"v": 1, "kind": "move", "direction": "NE"})


def test_unknown_field_is_rejected():
    with pytest.raises(ProtocolValidationError, match="unknown action field"):
        decode_action({"v": 1, "kind": "move", "direction": "N", "speed": 2})


def test_missing_field_is_rejected():
    with pytest.raises(ProtocolValidationError, match="missing action field"):
        decode_action({"v": 1, "kind": "move"})


@pytest.mark.parametrize(
    "cell", [[1], [1, 2, 3], "1,2", [1, "2"], [1, True], {"row": 1}]
)
def test_invalid_coordinate_is_rejected(cell):
    with pytest.raises(ProtocolValidationError, match="cell"):
        decode_action({"v": 1, "kind": "place_barrier", "cell": cell})


def test_non_object_action_is_rejected():
    with pytest.raises(ProtocolValidationError, match="must be an object"):
        decode_action(["move", "N"])  # type: ignore[arg-type]


def test_codec_accepts_no_hidden_state_field():
    """No way to smuggle a position or board state through an action."""
    for extra in ("position", "opponent_position", "board", "state"):
        with pytest.raises(ProtocolValidationError, match="unknown action field"):
            decode_action({"v": 1, "kind": "move", "direction": "N", extra: [0, 0]})


def test_codec_does_not_validate_board_legality():
    """Out-of-range coordinates decode fine: bounds need a board, and the
    domain owns that. The codec's contract is well-formedness only."""
    action = decode_action({"v": 1, "kind": "place_barrier", "cell": [99, 99]})
    assert action == PlaceBarrier(Coordinate(99, 99))
