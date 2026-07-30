"""Append-only audit log writer.

Append-only is enforced by construction: the file is opened in ``"a"`` mode,
never ``"w"``, there is no update or delete method, and each line is flushed
before the call returns. A record that reached the disk cannot be revised by
this class.

Privacy schedule (E-18, Ch. 5 PDF p. 51)
----------------------------------------
Before a reveal, the log may hold commitments, message ids and protocol state.
It must **not** hold the local action, its target, the local nonce, or anything
about the opponent's unrevealed move -- a log containing the action alongside
the commitment would defeat the commitment entirely for anyone reading the file.

After a reveal, the action and hint may be recorded, because they are already
public. **Nonces are recorded only in the final-reveal record**, at the end of
the match, which is precisely when the PDF discloses them.

:meth:`AuditLog.append` enforces this rather than trusting callers: a payload
carrying a nonce outside a final-reveal event raises.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from police_thief.audit.chain import GENESIS_HASH, compute_record_hash
from police_thief.audit.exceptions import AuditPrivacyError
from police_thief.audit.records import (
    AUDIT_SCHEMA_VERSION,
    AuditEventType,
    AuditRecord,
)

FORBIDDEN_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        # Secrets (E-39)
        "credentials", "credentials_path", "token_path", "access_token",
        "refresh_token", "client_secret", "api_key", "password",
        # Local truth (E-9)
        "opponent_position", "opponent_cell", "thief_position",
        "cop_position", "global_state", "board_state", "ground_truth",
    }
)

NONCE_BEARING_EVENTS: frozenset[str] = frozenset(
    {AuditEventType.FINAL_REVEAL.value}
)
"""The only event type whose payload may carry nonces (E-18)."""


@dataclass
class AuditLog:
    """Hash-chained append-only JSONL log for one peer."""

    path: Path
    game_id: str
    role: str
    sub_game: int = 1
    _previous_hash: str = field(default=GENESIS_HASH, init=False)
    _event_ids: set[str] = field(default_factory=set, init=False)
    _count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def previous_hash(self) -> str:
        return self._previous_hash

    @property
    def count(self) -> int:
        return self._count

    # ------------------------------------------------------------------

    def append(
        self,
        event_type: AuditEventType,
        payload: Mapping[str, Any] | None = None,
        *,
        turn_number: int | None = None,
        event_id: str | None = None,
        timestamp: str | None = None,
    ) -> AuditRecord:
        """Append one record and return it."""
        body = dict(payload or {})
        self._assert_permitted(event_type, body)

        record_id = event_id or str(uuid.uuid4())
        if record_id in self._event_ids:
            raise AuditPrivacyError(
                f"event_id {record_id!r} already used; ids must be unique so a "
                f"duplicate cannot be passed off as a distinct event"
            )

        mapping: dict[str, Any] = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "event_id": record_id,
            "game_id": self.game_id,
            "role": self.role,
            "sub_game": self.sub_game,
            "turn_number": turn_number,
            "event_type": event_type.value,
            "timestamp": timestamp or _utc_now(),
            "previous_event_hash": self._previous_hash,
            "payload": body,
        }
        mapping["current_event_hash"] = compute_record_hash(mapping)

        line = json.dumps(mapping, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

        self._previous_hash = mapping["current_event_hash"]
        self._event_ids.add(record_id)
        self._count += 1

        return AuditRecord(
            schema_version=mapping["schema_version"],
            event_id=mapping["event_id"],
            game_id=mapping["game_id"],
            role=mapping["role"],
            sub_game=mapping["sub_game"],
            turn_number=mapping["turn_number"],
            event_type=mapping["event_type"],
            timestamp=mapping["timestamp"],
            previous_event_hash=mapping["previous_event_hash"],
            current_event_hash=mapping["current_event_hash"],
            payload=body,
        )

    # ------------------------------------------------------------------

    def _assert_permitted(
        self, event_type: AuditEventType, payload: Mapping[str, Any]
    ) -> None:
        """Refuse forbidden content, rather than filtering it out.

        Filtering would let a caller believe it had recorded something it had
        not. Raising surfaces the mistake where it was made.
        """
        allows_nonce = event_type.value in NONCE_BEARING_EVENTS
        stack: list[Any] = [payload]

        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    lowered = key.lower()
                    if lowered in FORBIDDEN_PAYLOAD_KEYS:
                        raise AuditPrivacyError(
                            f"payload contains forbidden key {key!r}; secrets "
                            f"and opponent positions are never logged"
                        )
                    if lowered == "nonce" and not allows_nonce:
                        raise AuditPrivacyError(
                            f"payload of {event_type.value!r} contains a nonce; "
                            f"nonces are disclosed only at the final reveal "
                            f"(E-18), and logging one earlier would defeat the "
                            f"commitment it belongs to"
                        )
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
