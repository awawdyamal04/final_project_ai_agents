"""Data shapes for a sparring series (Phase C/D), split out of
:mod:`series_v3` to keep that file under the project's 150-line limit."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubGameRow:
    """One sub-game's machine-readable terminal-consensus record (Phase D):
    local terminal reason, remote terminal reason (read off the opponent's
    own audit ``result_claim``), audit status, and whether the two sides
    truly agree -- independent of, and never written into, the native
    protocol's own D-41 replay semantics."""

    sub_game_number: int
    role: str
    local_terminal: str | None
    remote_terminal: str | None
    audit_status: str  # "verified" | "unverified" | "no_audit"
    agreement: bool


@dataclass
class SeriesResult:
    game_id: str | None = None
    game_uid: str | None = None
    rows: list[SubGameRow] = field(default_factory=list)
    refusal: str | None = None
    settled: bool = False  # every requested sub-game completed and agreed
