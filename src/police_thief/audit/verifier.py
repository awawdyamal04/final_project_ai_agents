"""Independent audit-chain verifier.

Reads a peer's JSONL log and recomputes the whole chain from the genesis hash.
It shares nothing with the writer but the canonical serialiser and the hash
formula -- no shared state, no trusted summary -- so a log that verifies here
verifies on the strength of its own contents.

This is the **log-chain** verifier, not yet the full game replay. It answers
"has this file been altered since it was written?" It does not yet answer "do
these two logs describe a legal game?", which needs both peers' logs plus the
config and arrives in Phase 6.

Reports the **first** failing record and why. Ch. 7 (PDF p. 74) sets the
standard: *"the comparison is binary -- there is no 'almost matching'"*, and one
failure voids the whole match (E-19).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from police_thief.audit.chain import GENESIS_HASH, compute_record_hash
from police_thief.audit.exceptions import (
    AuditRecordSchemaError,
)
from police_thief.audit.records import validate_record_mapping

VERIFIED_OK = "Verified OK"
TAMPERED = "TAMPERED"


@dataclass(frozen=True, slots=True)
class ChainVerdict:
    """The result of verifying one log."""

    ok: bool
    records_checked: int
    failure_index: int | None = None
    reason: str | None = None
    failure_kind: str | None = None

    @property
    def stamp(self) -> str:
        """The banner Ch. 7 describes: green ``Verified OK`` or red ``TAMPERED``."""
        return VERIFIED_OK if self.ok else TAMPERED

    def __bool__(self) -> bool:
        return self.ok

    def describe(self) -> str:
        if self.ok:
            return f"{VERIFIED_OK} ({self.records_checked} records)"
        return (
            f"{TAMPERED} at record {self.failure_index} "
            f"[{self.failure_kind}]: {self.reason}"
        )


def verify_chain(records: Sequence[Any]) -> ChainVerdict:
    """Verify a sequence of decoded records."""
    previous = GENESIS_HASH
    seen_ids: set[str] = set()

    for index, raw in enumerate(records):
        try:
            validate_record_mapping(raw, index=index)
        except AuditRecordSchemaError as exc:
            return ChainVerdict(
                False, index, index, str(exc), "AuditRecordSchemaError"
            )

        if raw["event_id"] in seen_ids:
            return ChainVerdict(
                False,
                index,
                index,
                f"duplicate event_id {raw['event_id']!r}",
                "DuplicateAuditEventError",
            )
        seen_ids.add(raw["event_id"])

        # The chain link. A deleted, inserted or reordered record shows up here,
        # because each record names the hash it expects to follow.
        if raw["previous_event_hash"] != previous:
            return ChainVerdict(
                False,
                index,
                index,
                (
                    f"previous_event_hash {raw['previous_event_hash'][:12]}… "
                    f"does not match the preceding record's hash "
                    f"{previous[:12]}…; a record has been deleted, inserted or "
                    f"reordered"
                ),
                "AuditChainBreakError",
            )

        recomputed = compute_record_hash(raw)
        if recomputed != raw["current_event_hash"]:
            return ChainVerdict(
                False,
                index,
                index,
                (
                    f"recomputed hash {recomputed[:12]}… does not match the "
                    f"stored {raw['current_event_hash'][:12]}…; this record's "
                    f"contents were modified after it was written"
                ),
                "AuditHashMismatchError",
            )

        previous = raw["current_event_hash"]

    return ChainVerdict(True, len(records))


def verify_chain_file(path: str | Path) -> ChainVerdict:
    """Verify a JSONL log on disk.

    A malformed line is a failure, not something to skip: a verifier that
    tolerates unparseable input has a blind spot exactly where an attacker
    would aim.
    """
    path = Path(path)
    if not path.exists():
        return ChainVerdict(False, 0, None, f"no log at {path}", "FileNotFound")

    records: list[Any] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            return ChainVerdict(
                False,
                len(records),
                index,
                f"line {index} is not valid JSON: {exc}",
                "MalformedLine",
            )
    return verify_chain(records)


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read a log without verifying it. For tests that then tamper with it."""
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
