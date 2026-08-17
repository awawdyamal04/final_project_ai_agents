"""Closed schema for ``CAPTURE_CLAIM`` / ``CAPTURE_CLAIM_RESPONSE`` (E-21, E-22).

Mandatory shape (prd.md Sec 14.8, Correction 1 of the design-review pass):
the cop is the primary, mandatory initiator; the thief answers truthfully.
Field names are OUR design decision (prd.md Sec 14.0 [B]), not
lecturer-prescribed text.

The payload never carries a coordinate, a cell, or a nonce -- prd.md
Sec 14.6/14.7. ``turn_number``, ``sender_role`` and ``receiver_role`` are
not duplicated here: the envelope already carries them (``messages.py``).

``claim_kind`` vocabulary (``CLAIM_KINDS`` etc.) lives in
``domain/capture_claim.py``, re-exported here for convenience, since it is
fundamentally a labelling of :class:`~police_thief.domain.enums.CaptureReason`
-- a domain concept protocol depends on, not the reverse.

Validation (role checks, freshness, malformed-payload rejection) lives in
:mod:`police_thief.protocol.capture_claim_validation`, kept separate purely
to stay under the 150-line lecturer limit.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.domain.capture_claim import (
    CLAIM_KIND_BARRIER_ON_THIEF,
    CLAIM_KIND_LANDED,
    CLAIM_KIND_NO_LEGAL_MOVE,
    CLAIM_KINDS,
    claim_kind_for_reason,
    reason_for_claim_kind,
)

__all__ = [
    "CLAIM_KIND_BARRIER_ON_THIEF",
    "CLAIM_KIND_LANDED",
    "CLAIM_KIND_NO_LEGAL_MOVE",
    "CLAIM_KINDS",
    "VERDICT_AUDIT_REQUIRED",
    "VERDICT_CONFIRM",
    "VERDICT_DENY",
    "VERDICTS",
    "CaptureClaim",
    "CaptureClaimResponse",
    "claim_kind_for_reason",
    "reason_for_claim_kind",
]

VERDICT_CONFIRM = "confirm"
VERDICT_DENY = "deny"
VERDICT_AUDIT_REQUIRED = "audit_required"
"""The thief cannot locally determine the truth without opponent information
E-8/E-9 forbid it from holding (currently only the ``landed`` ground, which
needs the cop's true resulting position). Not a confirmation and not a
denial: no hidden data is revealed, gameplay continues, and the offline
replay/audit is authoritative for this claim (D-41 augmented)."""
VERDICTS: frozenset[str] = frozenset(
    {VERDICT_CONFIRM, VERDICT_DENY, VERDICT_AUDIT_REQUIRED}
)


@dataclass(frozen=True, slots=True)
class CaptureClaim:
    """A cop's declared suspicion. Always a belief, never a fact (E-9)."""

    claim_id: str
    sub_game: int
    turn: int
    claim_kind: str
    commitment: str

    def to_payload(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "sub_game": self.sub_game,
            "claim_kind": self.claim_kind,
            "commitment": self.commitment,
        }


@dataclass(frozen=True, slots=True)
class CaptureClaimResponse:
    """The thief's truthful answer -- ``confirm``/``deny``/``audit_required``
    only, prd.md Sec 14.6. ``audit_required`` is an honest "cannot verify
    live", not a third truth value."""

    claim_id: str
    sub_game: int
    turn: int
    verdict: str
    commitment: str

    def to_payload(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "sub_game": self.sub_game,
            "verdict": self.verdict,
            "commitment": self.commitment,
        }
