"""Live capture_claim orchestration (E-21, E-22): the shared runtime state
plus the cop-side half (declare a claim, accept the thief's response).

Primary, mandatory flow only (prd.md Sec 14.3/14.8, Correction 1) -- no
thief-initiated self-signal extension is implemented in this pass; its
absence does not affect E-21/E-22 compliance (prd.md Sec 14.8.1).

Owned by ``PeerOrchestrator`` as ``self.capture_claims``, composed exactly
like ``self.crypto``/``self.audit`` (D-44's sibling-module pattern) rather
than inlined into the orchestrator itself. The thief-side half
(``handle_claim``) lives in ``peer/capture_claim_thief.py``, split out
purely to stay under the 150-line lecturer limit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from police_thief.audit.capture_claim_records import claim_payload
from police_thief.audit.records import AuditEventType
from police_thief.audit.writer import AuditLog
from police_thief.crypto.capture_claim_seal import seal_claim
from police_thief.domain.enums import CaptureReason, Role
from police_thief.protocol.capture_claim import (
    VERDICT_CONFIRM,
    CaptureClaim,
    CaptureClaimResponse,
    claim_kind_for_reason,
)
from police_thief.protocol.capture_claim_validation import validate_response_envelope
from police_thief.protocol.messages import Envelope


@dataclass
class CaptureClaimRuntime:
    """Mandatory cop-initiates / thief-responds flow, plus CLAIM_PENDING_AUDIT."""

    game_id: str
    role: Role
    sub_game: int = 1
    audit: AuditLog | None = None

    pending: bool = field(default=False, init=False)
    """CLAIM_PENDING_AUDIT (prd.md Sec 14.13, a design decision -- not a
    formal ``PeerState``, a deliberate minimal-complexity choice). Set once
    a claim this peer made or answered was confirmed; the turn loop checks
    this and stops issuing new turns. ``final_reveal`` and mutual audit
    still run -- only the turn loop is affected."""

    responses: dict[str, CaptureClaimResponse] = field(
        default_factory=dict, init=False
    )
    """Answered claims, keyed by ``claim_id``, for idempotent re-delivery."""

    # ------------------------------------------------------------------
    # Cop side: always a belief, never a fact (E-9)
    # ------------------------------------------------------------------

    def build_claim(self, *, turn: int, reason: CaptureReason) -> CaptureClaim:
        """Declare a suspected capture. The trigger heuristic (*when* to
        call this) is intentionally not decided here -- prd.md Sec 14.17
        [C]; a caller (test, or a future strategy layer) supplies the
        ground it believes applies."""
        claim_id = str(uuid.uuid4())
        kind = claim_kind_for_reason(reason)
        commitment = seal_claim(
            game_id=self.game_id,
            sub_game=self.sub_game,
            turn=turn,
            claimant_role=self.role.value,
            claim_kind=kind,
            claim_id=claim_id,
        )
        claim = CaptureClaim(
            claim_id=claim_id,
            sub_game=self.sub_game,
            turn=turn,
            claim_kind=kind,
            commitment=commitment,
        )
        if self.audit is not None:
            self.audit.append(
                AuditEventType.CAPTURE_CLAIM,
                claim_payload(claim, claimant_role=self.role.value),
                turn_number=turn,
            )
        return claim

    def record_response(self, envelope: Envelope) -> CaptureClaimResponse:
        """Cop side: accept the thief's ``CAPTURE_CLAIM_RESPONSE``."""
        response = validate_response_envelope(envelope)
        if response.verdict == VERDICT_CONFIRM:
            self.pending = True
        return response
