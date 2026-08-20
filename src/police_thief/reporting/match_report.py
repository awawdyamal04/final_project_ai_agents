"""Post-match JSON report + local ``results/league/`` index (league
readiness Priority 5/6).

Built entirely from what a single live peer legitimately knows about its own
match. It never invents a winner or a score: those are D-41's job, decided
offline by the two-log replay, which this module does not import (E-8/E-9 --
see ``tests/replay/test_two_log_replay.py::test_live_peer_never_imports_the_replay``).
Reporting a match never fabricates a result -- callers only construct a
:class:`MatchReport` from a match that actually ran.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEAGUE_DIR = Path("results/league")
INDEX_CSV = LEAGUE_DIR / "index.csv"
INDEX_FIELDS: tuple[str, ...] = (
    "timestamp", "game_id", "opponent_team", "our_role", "opponent_url",
    "turns_played", "exit_status", "audit_status", "replay_status",
    "gmail_status",
)

REPLAY_PENDING = (
    "pending offline replay -- a live peer cannot verify its own winner "
    "(E-8/E-9, D-41)"
)


@dataclass
class MatchReport:
    """One match, from this peer's own honest point of view."""

    game_id: str
    role: str
    opponent_url: str
    opponent_team: str
    turns_played: int
    exit_status: str  # "MATCH COMPLETE" | "TECHNICAL LOSS"
    audit_status: str
    replay_status: str = REPLAY_PENDING
    score: str = "pending offline replay"
    gmail_status: str = "not attempted"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_email_dict(self) -> dict[str, Any]:
        """The payload to email, deliberately excluding ``gmail_status``.

        The email is composed and sent in one step, before this peer knows
        whether the send itself will succeed -- there is no truthful value
        ``gmail_status`` could hold inside the message it is part of
        delivering. Omitting the field (rather than filling in a guess) is
        what stops a stale or pre-send value from ever reaching the inbox;
        the locally persisted JSON (``write_report``) is the one place that
        does carry the final, honest status, written *after* the send
        attempt completes.
        """
        return {k: v for k, v in self.to_dict().items() if k != "gmail_status"}


def write_report(report: MatchReport) -> Path:
    """Always write the JSON, unconditionally -- a missing mailer or a
    replay that has not run yet must never mean the result is lost."""
    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    safe_ts = report.timestamp.replace(":", "-")
    path = LEAGUE_DIR / f"{report.game_id}_{report.role}_{safe_ts}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    _append_index(report)
    return path


def _append_index(report: MatchReport) -> None:
    is_new = not INDEX_CSV.exists()
    row: Mapping[str, Any] = {
        "timestamp": report.timestamp,
        "game_id": report.game_id,
        "opponent_team": report.opponent_team,
        "our_role": report.role,
        "opponent_url": report.opponent_url,
        "turns_played": report.turns_played,
        "exit_status": report.exit_status,
        "audit_status": report.audit_status,
        "replay_status": report.replay_status,
        "gmail_status": report.gmail_status,
    }
    with INDEX_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)
