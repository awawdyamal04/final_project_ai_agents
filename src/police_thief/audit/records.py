"""Audit record schema.

Closed key set, validated on read as well as write: a verifier that accepts a
record it cannot fully account for is not verifying anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from police_thief.audit.exceptions import AuditRecordSchemaError

AUDIT_SCHEMA_VERSION = "1.0"

RECORD_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "event_id",
        "game_id",
        "role",
        "sub_game",
        "turn_number",
        "event_type",
        "timestamp",
        "previous_event_hash",
        "current_event_hash",
        "payload",
    }
)


class AuditEventType(str, Enum):
    """What happened. A closed set, so an unknown type fails validation."""

    SUB_GAME_START = "sub_game_start"
    STEP_ZERO = "step_zero"
    LOCAL_COMMIT = "local_commit"
    OPPONENT_COMMIT = "opponent_commit"
    COMMIT_ACKNOWLEDGED = "commit_acknowledged"
    LOCAL_REVEAL = "local_reveal"
    OPPONENT_REVEAL = "opponent_reveal"
    TURN_APPLIED = "turn_applied"
    TURN_FAILED = "turn_failed"
    FINAL_REVEAL = "final_reveal"
    AUDIT_RESULT = "audit_result"
    SUB_GAME_END = "sub_game_end"

    # --- capture_claim (E-21, E-22) -- see peer/capture_claim_runtime.py -
    CAPTURE_CLAIM = "capture_claim"
    CAPTURE_CLAIM_RESPONSE = "capture_claim_response"


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """One hash-chained entry."""

    schema_version: str
    event_id: str
    game_id: str
    role: str
    sub_game: int
    turn_number: int | None
    event_type: str
    timestamp: str
    previous_event_hash: str
    current_event_hash: str
    payload: Mapping[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "game_id": self.game_id,
            "role": self.role,
            "sub_game": self.sub_game,
            "turn_number": self.turn_number,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "previous_event_hash": self.previous_event_hash,
            "current_event_hash": self.current_event_hash,
            "payload": dict(self.payload),
        }


def validate_record_mapping(raw: Any, *, index: int = -1) -> None:
    """Check a decoded record against the closed schema."""
    where = f"record {index}" if index >= 0 else "record"

    if not isinstance(raw, dict):
        raise AuditRecordSchemaError(
            f"{where}: must be an object, got {type(raw).__name__}"
        )

    for unknown in sorted(set(raw) - RECORD_KEYS):
        raise AuditRecordSchemaError(f"{where}: unknown field {unknown!r}")
    for missing in sorted(RECORD_KEYS - set(raw)):
        raise AuditRecordSchemaError(f"{where}: missing field {missing!r}")

    if raw["schema_version"] != AUDIT_SCHEMA_VERSION:
        raise AuditRecordSchemaError(
            f"{where}: unsupported schema version {raw['schema_version']!r}"
        )

    for key in (
        "event_id",
        "game_id",
        "role",
        "event_type",
        "timestamp",
        "previous_event_hash",
        "current_event_hash",
    ):
        if not isinstance(raw[key], str) or not raw[key]:
            raise AuditRecordSchemaError(
                f"{where}: {key} must be a non-empty string"
            )

    try:
        AuditEventType(raw["event_type"])
    except ValueError as exc:
        raise AuditRecordSchemaError(
            f"{where}: unknown event_type {raw['event_type']!r}"
        ) from exc

    for key in ("previous_event_hash", "current_event_hash"):
        value = raw[key]
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise AuditRecordSchemaError(
                f"{where}: {key} must be 64 lowercase hex characters"
            )

    if isinstance(raw["sub_game"], bool) or not isinstance(raw["sub_game"], int):
        raise AuditRecordSchemaError(f"{where}: sub_game must be an integer")

    turn = raw["turn_number"]
    if turn is not None and (
        isinstance(turn, bool) or not isinstance(turn, int) or turn < 0
    ):
        raise AuditRecordSchemaError(
            f"{where}: turn_number must be a non-negative integer or null"
        )

    if not isinstance(raw["payload"], dict):
        raise AuditRecordSchemaError(f"{where}: payload must be an object")


def record_from_mapping(raw: Mapping[str, Any], *, index: int = -1) -> AuditRecord:
    validate_record_mapping(raw, index=index)
    return AuditRecord(
        schema_version=raw["schema_version"],
        event_id=raw["event_id"],
        game_id=raw["game_id"],
        role=raw["role"],
        sub_game=raw["sub_game"],
        turn_number=raw["turn_number"],
        event_type=raw["event_type"],
        timestamp=raw["timestamp"],
        previous_event_hash=raw["previous_event_hash"],
        current_event_hash=raw["current_event_hash"],
        payload=dict(raw["payload"]),
    )
