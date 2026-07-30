"""Wire message schemas: closed key sets, versions, roles, types."""

from __future__ import annotations

import pytest

from police_thief.domain.enums import Role
from police_thief.protocol.codec import decode_envelope, encode_envelope
from police_thief.protocol.exceptions import (
    ProtocolValidationError,
    UnknownMessageTypeError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemaVersionError,
)
from police_thief.protocol.messages import (
    ENVELOPE_KEYS,
    Envelope,
    MessageType,
    envelope_from_wire,
    new_envelope,
)
from police_thief.protocol.versions import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    is_protocol_compatible,
)


def hello() -> Envelope:
    return new_envelope(
        game_id="g1",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.HELLO,
        payload={
            "peer_name": "team-a",
            "software_version": "0.2.0",
            "capabilities": ["handshake.v1", "canonical-json.v1"],
        },
    )


def test_valid_message_round_trips():
    original = hello()
    restored = decode_envelope(encode_envelope(original))
    assert restored == original


def test_envelope_key_set_is_exactly_the_schema():
    assert set(hello().to_wire()) == set(ENVELOPE_KEYS)
    assert ENVELOPE_KEYS == {
        "schema_version",
        "protocol_version",
        "message_id",
        "game_id",
        "sender_role",
        "receiver_role",
        "message_type",
        "turn_number",
        "timestamp",
        "payload",
    }


@pytest.mark.parametrize("field", sorted(ENVELOPE_KEYS))
def test_missing_envelope_field_is_rejected(field):
    wire = hello().to_wire()
    del wire[field]
    with pytest.raises(ProtocolValidationError, match="missing envelope field"):
        envelope_from_wire(wire)


def test_unknown_envelope_field_is_rejected():
    wire = hello().to_wire()
    wire["extra"] = 1
    with pytest.raises(ProtocolValidationError, match="unknown envelope field"):
        envelope_from_wire(wire)


def test_unsupported_schema_version_is_rejected():
    wire = hello().to_wire()
    wire["schema_version"] = "9.9"
    with pytest.raises(UnsupportedSchemaVersionError):
        envelope_from_wire(wire)


def test_incompatible_protocol_version_is_rejected():
    wire = hello().to_wire()
    wire["protocol_version"] = "2.0"
    with pytest.raises(UnsupportedProtocolVersionError):
        envelope_from_wire(wire)


def test_minor_protocol_differences_are_compatible():
    """Additive minor versions must interoperate; a flag day between two teams
    who cannot deploy simultaneously is not workable."""
    assert is_protocol_compatible("1.7", "1.0")
    assert not is_protocol_compatible("2.0", "1.0")
    assert not is_protocol_compatible("", "1.0")


def test_unknown_message_type_is_rejected():
    wire = hello().to_wire()
    wire["message_type"] = "launch_missiles"
    with pytest.raises(UnknownMessageTypeError):
        envelope_from_wire(wire)


def test_unknown_role_is_rejected():
    wire = hello().to_wire()
    wire["sender_role"] = "referee"
    with pytest.raises(ProtocolValidationError, match="roles must be"):
        envelope_from_wire(wire)


@pytest.mark.parametrize("field", ["message_id", "game_id", "timestamp"])
def test_empty_identity_field_is_rejected(field):
    wire = hello().to_wire()
    wire[field] = ""
    with pytest.raises(ProtocolValidationError, match="non-empty"):
        envelope_from_wire(wire)


@pytest.mark.parametrize("bad", ["3", 3.5, True, -1])
def test_bad_turn_number_is_rejected(bad):
    wire = hello().to_wire()
    wire["turn_number"] = bad
    with pytest.raises(ProtocolValidationError, match="turn_number"):
        envelope_from_wire(wire)


def test_turn_number_may_be_null():
    wire = hello().to_wire()
    wire["turn_number"] = None
    assert envelope_from_wire(wire).turn_number is None


# ----------------------------------------------------------------------
# Payload schemas
# ----------------------------------------------------------------------


def test_unknown_payload_field_is_rejected():
    with pytest.raises(ProtocolValidationError, match="unknown payload field"):
        new_envelope(
            game_id="g1",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.READY,
            payload={"sneaky": 1},
        )


def test_missing_payload_field_is_rejected():
    with pytest.raises(ProtocolValidationError, match="missing payload field"):
        new_envelope(
            game_id="g1",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.CONFIG_HASH,
            payload={"config_sha256": "abc"},
        )


def test_wrong_payload_type_is_rejected():
    with pytest.raises(ProtocolValidationError, match="expected str"):
        new_envelope(
            game_id="g1",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.CONFIG_HASH,
            payload={"config_sha256": 123, "config_schema_version": "1.2"},
        )


def test_bool_is_not_accepted_where_a_string_belongs():
    with pytest.raises(ProtocolValidationError, match="got bool"):
        new_envelope(
            game_id="g1",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.ERROR,
            payload={"code": True, "detail": "x"},
        )


def test_reply_swaps_sender_and_receiver():
    reply = hello().reply(MessageType.ACK, {"acknowledged_message_id": "m1"})
    assert reply.sender_role is Role.THIEF
    assert reply.receiver_role is Role.POLICE
    assert reply.game_id == "g1"


def test_envelope_is_frozen():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        hello().game_id = "other"  # type: ignore[misc]


def test_defaults_are_the_current_versions():
    envelope = hello()
    assert envelope.schema_version == SCHEMA_VERSION
    assert envelope.protocol_version == PROTOCOL_VERSION
