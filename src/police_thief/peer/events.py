"""Operational event log.

Append-only JSON Lines, one object per line, flushed on write. JSONL rather than
a JSON array because a peer that crashes mid-write must leave a readable file:
a truncated array is unparseable, a truncated JSONL file is valid up to its last
complete line -- which is what makes the watchdog's controlled data extraction
(E-7) worth anything.

**This is not the cryptographic audit chain.** The match log required by E-36
and consumed by the replay verifier (E-20) is hash-chained, sealed at end of
sub-game, and defined in PROTOCOL.md section 11. It arrives in Phase 5. This
file is operational telemetry: connections, retries, state transitions. It
proves nothing about the game and is not evidence in an audit.

Redaction is enforced, not merely intended. :func:`_assert_no_secrets` refuses
to write a record containing a credential-shaped key, so a careless caller gets
an exception rather than a leaked token in a file that later gets committed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

FORBIDDEN_EVENT_KEYS: frozenset[str] = frozenset(
    {
        "credentials",
        "credentials_path",
        "token",
        "token_path",
        "access_token",
        "refresh_token",
        "client_secret",
        "api_key",
        "password",
        "authorization",
        "opponent_position",
        "opponent_cell",
        "thief_position",
        "cop_position",
        "global_state",
        "board_state",
    }
)
"""Keys that must never appear in an operational record.

Two families, both banned for the same reason -- a log is a file that gets
copied, shared and sometimes committed. Credentials (E-39) and the opponent's
true position (E-9) are the two things whose leakage is unrecoverable.
"""


class EventSink(Protocol):
    """Somewhere operational events go."""

    def emit(self, event: str, **fields: Any) -> None: ...


def _assert_no_secrets(record: dict[str, Any]) -> None:
    """Refuse to write a record with a forbidden key, at any depth."""
    stack: list[Any] = [record]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key.lower() in FORBIDDEN_EVENT_KEYS:
                    raise ValueError(
                        f"operational log record contains forbidden key "
                        f"{key!r}; secrets and opponent positions must never "
                        f"be logged"
                    )
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)


@dataclass
class JsonlEventSink:
    """Writes events to a JSONL file, and optionally echoes a summary."""

    path: Path
    role: str
    game_id: str
    echo: bool = False
    records: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields: Any) -> None:
        record = {
            "event": event,
            "role": self.role,
            "game_id": self.game_id,
            **fields,
        }
        _assert_no_secrets(record)
        self.records.append(record)
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        if self.echo:
            print(f"  [{self.role}] {event}", flush=True)


@dataclass
class MemoryEventSink:
    """Collects events in memory. For tests."""

    records: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event: str, **fields: Any) -> None:
        record = {"event": event, **fields}
        _assert_no_secrets(record)
        self.records.append(record)

    def events_named(self, name: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r["event"] == name]

    def names(self) -> list[str]:
        return [r["event"] for r in self.records]


class NullEventSink:
    """Discards everything. For code paths that must not require a log."""

    def emit(self, event: str, **fields: Any) -> None:
        return None
