"""Wire message envelope and payloads.

Closed schema throughout. Unknown keys are rejected rather than ignored,
following the same reasoning as the configuration loader: a silently-dropped
field is how two peers end up believing they agreed about something they did
not.

**Nothing here can carry the opponent's true position.** There is no field for
a position at all -- not in the envelope, not in any payload. Positions reach
the wire only in Phase 5, sealed inside a commit and revealed under the
commit-reveal protocol. Asserted by
``tests/peer/test_information_boundary.py::test_no_payload_schema_accepts_a_position``.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from police_thief.domain.enums import Role
from police_thief.protocol.exceptions import (
    ProtocolValidationError,
    UnknownMessageTypeError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemaVersionError,
)
from police_thief.protocol.versions import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    is_protocol_compatible,
    is_schema_supported,
)


class MessageType(str, Enum):
    """The closed set of Phase 2 message types.

    Turn and commit-reveal messages are deliberately absent. Adding a
    ``TURN_INTENT`` placeholder now would create a message type no state
    accepts and no code produces -- untestable by construction. They arrive in
    Phase 5 together with the cryptography that gives them meaning.
    """

    HEALTH_CHECK = "health_check"
    HELLO = "hello"
    CONFIG_HASH = "config_hash"
    CONFIG_ACCEPTED = "config_accepted"
    CONFIG_REJECTED = "config_rejected"
    READY = "ready"
    ACK = "ack"
    ERROR = "error"
    GAME_FINISHED = "game_finished"
    SHUTDOWN = "shutdown"

    # --- Phase 3: the cryptographic turn (Ch. 5, PDF pp. 50-51) ---------
    COMMIT = "commit"
    """Carries the digest and nothing else."""

    COMMIT_ACK = "commit_ack"
    """"Prevents the sender retreating from its commitment, and guarantees the
    reveal happens only once both sides have fixed their moves" (PDF p. 51)."""

    REVEAL = "reveal"
    """Action and hint. **No nonce** -- it "remains hidden at this stage"
    (E-18, PDF p. 51)."""

    REVEAL_ACK = "reveal_ack"

    FINAL_REVEAL = "final_reveal"
    """All nonces, at end of match: "only at the end of the whole game are all
    Nonce values revealed, for full mutual audit" (PDF p. 51)."""

    FINAL_REVEAL_ACK = "final_reveal_ack"

    TURN_ABORT = "turn_abort"
    CRYPTO_ERROR = "crypto_error"


ENVELOPE_KEYS: frozenset[str] = frozenset(
    {
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
)


# ----------------------------------------------------------------------
# Payload schemas -- one closed key set per message type
# ----------------------------------------------------------------------

_PAYLOAD_SCHEMAS: dict[MessageType, dict[str, tuple[type | tuple[type, ...], bool]]] = {
    # key -> (type, required)
    MessageType.HEALTH_CHECK: {},
    MessageType.HELLO: {
        "peer_name": (str, True),
        "software_version": (str, True),
        "capabilities": (list, True),
    },
    MessageType.CONFIG_HASH: {
        "config_sha256": (str, True),
        "config_schema_version": (str, True),
    },
    MessageType.CONFIG_ACCEPTED: {
        "config_sha256": (str, True),
    },
    MessageType.CONFIG_REJECTED: {
        "reason": (str, True),
        "our_config_sha256": (str, True),
        "their_config_sha256": (str, True),
    },
    MessageType.READY: {},
    MessageType.ACK: {
        "acknowledged_message_id": (str, True),
    },
    MessageType.ERROR: {
        "code": (str, True),
        "detail": (str, True),
    },
    MessageType.GAME_FINISHED: {
        "reason": (str, True),
    },
    MessageType.SHUTDOWN: {
        "reason": (str, True),
    },
    # --- Phase 3 -------------------------------------------------------
    # COMMIT carries the digest ONLY. No action, no kind, no coordinate, no
    # nonce, no length hint. The move space is small enough to enumerate, so
    # anything narrowing it would defeat the commitment.
    MessageType.COMMIT: {
        "commitment": (str, True),
        "commitment_schema": (str, True),
    },
    MessageType.COMMIT_ACK: {
        "commitment": (str, True),
        "locked": (bool, True),
    },
    # REVEAL carries the sealed record WITHOUT its nonce (E-18).
    MessageType.REVEAL: {
        "sealed": (dict, True),
    },
    MessageType.REVEAL_ACK: {
        "accepted": (bool, True),
    },
    MessageType.FINAL_REVEAL: {
        "records": (list, True),
    },
    MessageType.FINAL_REVEAL_ACK: {
        "audit": (str, True),
        "verified_turns": (int, True),
    },
    MessageType.TURN_ABORT: {
        "reason": (str, True),
    },
    MessageType.CRYPTO_ERROR: {
        "code": (str, True),
        "detail": (str, True),
    },
}

CRYPTO_MESSAGE_TYPES: frozenset[MessageType] = frozenset(
    {
        MessageType.COMMIT,
        MessageType.COMMIT_ACK,
        MessageType.REVEAL,
        MessageType.REVEAL_ACK,
        MessageType.FINAL_REVEAL,
        MessageType.FINAL_REVEAL_ACK,
        MessageType.TURN_ABORT,
        MessageType.CRYPTO_ERROR,
    }
)

TURN_BEARING_MESSAGE_TYPES: frozenset[MessageType] = frozenset(
    {
        MessageType.COMMIT,
        MessageType.COMMIT_ACK,
        MessageType.REVEAL,
        MessageType.REVEAL_ACK,
    }
)
"""Types that must carry a ``turn_number``; validated on ingress."""


@dataclass(frozen=True, slots=True)
class Envelope:
    """A validated wire message.

    Frozen: a message that can be edited after validation is a message whose
    validation means nothing.
    """

    message_id: str
    game_id: str
    sender_role: Role
    receiver_role: Role
    message_type: MessageType
    timestamp: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    turn_number: int | None = None
    schema_version: str = SCHEMA_VERSION
    protocol_version: str = PROTOCOL_VERSION

    def to_wire(self) -> dict[str, Any]:
        """The JSON-ready mapping. Key set is exactly ``ENVELOPE_KEYS``."""
        return {
            "schema_version": self.schema_version,
            "protocol_version": self.protocol_version,
            "message_id": self.message_id,
            "game_id": self.game_id,
            "sender_role": self.sender_role.value,
            "receiver_role": self.receiver_role.value,
            "message_type": self.message_type.value,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }

    def reply(
        self,
        message_type: MessageType,
        payload: Mapping[str, Any] | None = None,
        *,
        message_id: str | None = None,
    ) -> Envelope:
        """Build a response, with sender and receiver swapped."""
        return new_envelope(
            game_id=self.game_id,
            sender_role=self.receiver_role,
            receiver_role=self.sender_role,
            message_type=message_type,
            payload=payload,
            turn_number=self.turn_number,
            message_id=message_id,
        )


def utc_now() -> str:
    """RFC 3339 UTC timestamp.

    Informational only. It is never hashed and never used to order messages --
    two peers on two machines have two clocks, and Ch. 11 (PDF p. 109) names a
    drifting local clock as one of the real-world failures the system must
    survive. Ordering comes from ``turn_number`` and the state machine.
    """
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def new_message_id() -> str:
    return str(uuid.uuid4())


def new_envelope(
    *,
    game_id: str,
    sender_role: Role,
    receiver_role: Role,
    message_type: MessageType,
    payload: Mapping[str, Any] | None = None,
    turn_number: int | None = None,
    message_id: str | None = None,
    timestamp: str | None = None,
) -> Envelope:
    """Construct an envelope, validating the payload against its schema."""
    envelope = Envelope(
        message_id=message_id or new_message_id(),
        game_id=game_id,
        sender_role=sender_role,
        receiver_role=receiver_role,
        message_type=message_type,
        timestamp=timestamp or utc_now(),
        payload=dict(payload or {}),
        turn_number=turn_number,
    )
    validate_payload(envelope.message_type, envelope.payload)
    return envelope


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def validate_payload(
    message_type: MessageType, payload: Mapping[str, Any]
) -> None:
    """Check a payload against the closed schema for its message type."""
    if not isinstance(payload, dict):
        raise ProtocolValidationError(
            f"payload must be an object, got {type(payload).__name__}"
        )

    schema = _PAYLOAD_SCHEMAS[message_type]
    allowed = set(schema)

    for unknown in sorted(set(payload) - allowed):
        raise ProtocolValidationError(
            f"{message_type.value}: unknown payload field {unknown!r}; "
            f"allowed: {sorted(allowed)}"
        )

    for key, (expected_type, required) in schema.items():
        if key not in payload:
            if required:
                raise ProtocolValidationError(
                    f"{message_type.value}: missing payload field {key!r}"
                )
            continue
        value = payload[key]
        if isinstance(value, bool) and expected_type is not bool:
            raise ProtocolValidationError(
                f"{message_type.value}.{key}: expected "
                f"{_type_name(expected_type)}, got bool"
            )
        if not isinstance(value, expected_type):
            raise ProtocolValidationError(
                f"{message_type.value}.{key}: expected "
                f"{_type_name(expected_type)}, got {type(value).__name__}"
            )


def _type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(t.__name__ for t in expected)
    return expected.__name__


def envelope_from_wire(raw: Any) -> Envelope:
    """Validate a decoded mapping and build an :class:`Envelope`.

    Rejects, in this order: non-object, unknown keys, missing keys, unsupported
    schema version, incompatible protocol version, unknown message type, bad
    role values, bad types, then the payload schema. The order is from the most
    structural failure to the most specific, so the error a peer sees names the
    outermost thing that is wrong.
    """
    if not isinstance(raw, dict):
        raise ProtocolValidationError(
            f"envelope must be an object, got {type(raw).__name__}"
        )

    present = set(raw)
    for unknown in sorted(present - ENVELOPE_KEYS):
        raise ProtocolValidationError(f"unknown envelope field {unknown!r}")
    for missing in sorted(ENVELOPE_KEYS - present):
        raise ProtocolValidationError(f"missing envelope field {missing!r}")

    schema_version = raw["schema_version"]
    if not isinstance(schema_version, str) or not is_schema_supported(schema_version):
        raise UnsupportedSchemaVersionError(
            f"unsupported envelope schema version {schema_version!r}; "
            f"this peer speaks {SCHEMA_VERSION}"
        )

    protocol_version = raw["protocol_version"]
    if not isinstance(protocol_version, str) or not is_protocol_compatible(
        protocol_version
    ):
        raise UnsupportedProtocolVersionError(
            f"incompatible protocol version {protocol_version!r}; "
            f"this peer speaks {PROTOCOL_VERSION}"
        )

    try:
        message_type = MessageType(raw["message_type"])
    except ValueError as exc:
        raise UnknownMessageTypeError(
            f"unknown message type {raw['message_type']!r}"
        ) from exc

    try:
        sender_role = Role(raw["sender_role"])
        receiver_role = Role(raw["receiver_role"])
    except ValueError as exc:
        raise ProtocolValidationError(
            f"roles must be one of {sorted(r.value for r in Role)}"
        ) from exc

    for key in ("message_id", "game_id", "timestamp"):
        if not isinstance(raw[key], str) or not raw[key]:
            raise ProtocolValidationError(f"{key} must be a non-empty string")

    turn_number = raw["turn_number"]
    if turn_number is not None:
        if isinstance(turn_number, bool) or not isinstance(turn_number, int):
            raise ProtocolValidationError(
                f"turn_number must be an integer or null, "
                f"got {type(turn_number).__name__}"
            )
        if turn_number < 0:
            raise ProtocolValidationError("turn_number must not be negative")

    if message_type in TURN_BEARING_MESSAGE_TYPES and turn_number is None:
        raise ProtocolValidationError(
            f"{message_type.value} must carry a turn_number; a commitment or "
            f"reveal not bound to a turn could be replayed into another one"
        )

    validate_payload(message_type, raw["payload"])

    return Envelope(
        message_id=raw["message_id"],
        game_id=raw["game_id"],
        sender_role=sender_role,
        receiver_role=receiver_role,
        message_type=message_type,
        timestamp=raw["timestamp"],
        payload=dict(raw["payload"]),
        turn_number=turn_number,
        schema_version=schema_version,
        protocol_version=protocol_version,
    )
