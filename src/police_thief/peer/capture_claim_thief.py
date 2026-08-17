"""Thief-side half of live capture_claim handling (E-21): answer a cop's
claim truthfully.

Split out of ``peer/capture_claim_runtime.py`` purely to stay under the
150-line lecturer limit -- same feature, same ``CaptureClaimRuntime``
object, just the half that computes and logs the response.

``CaptureClaimUnverifiableError`` (currently only the ``landed`` ground
without an explicit ``movement``) is caught here, not left to propagate: it
must never escape this handler and crash the peer or break the game loop.
It is mapped to ``VERDICT_AUDIT_REQUIRED`` -- an honest "cannot verify live
without forbidden opponent information" (E-8/E-9), never a guessed
confirm/deny. See ``protocol/capture_claim.py``'s docstring for that value.
"""

from __future__ import annotations

from police_thief.audit.capture_claim_records import response_payload
from police_thief.audit.records import AuditEventType
from police_thief.config.models import SharedConfig
from police_thief.crypto.capture_claim_seal import seal_response
from police_thief.domain.capture_claim import thief_truthful_verdict, verdict_confirms_claim
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.exceptions import CaptureClaimUnverifiableError
from police_thief.domain.simultaneity import (
    DEFAULT_SIMULTANEITY_POLICY,
    SimultaneityPolicy,
    TurnMovement,
)
from police_thief.domain.state import LocalState
from police_thief.peer.capture_claim_runtime import CaptureClaimRuntime
from police_thief.protocol.capture_claim import (
    VERDICT_AUDIT_REQUIRED,
    VERDICT_CONFIRM,
    VERDICT_DENY,
    CaptureClaimResponse,
)
from police_thief.protocol.capture_claim_validation import (
    validate_claim_envelope,
    validate_claim_freshness,
)
from police_thief.protocol.messages import Envelope


def handle_claim(
    runtime: CaptureClaimRuntime,
    envelope: Envelope,
    *,
    thief_state: LocalState,
    config: SharedConfig,
    latest_completed_turn: int,
    barrier_cell: Coordinate | None = None,
    movement: TurnMovement | None = None,
    policy: SimultaneityPolicy = DEFAULT_SIMULTANEITY_POLICY,
) -> CaptureClaimResponse:
    """Answer a cop's claim truthfully. Idempotent: re-sending the same
    ``claim_id`` returns the already-logged response rather than
    recomputing (and re-appending) a second one."""
    claim = validate_claim_envelope(envelope)

    cached = runtime.responses.get(claim.claim_id)
    if cached is not None:
        return cached

    validate_claim_freshness(claim.turn, latest_completed_turn)

    try:
        verdict = thief_truthful_verdict(
            claim.claim_kind,
            thief_state,
            config,
            barrier_cell=barrier_cell,
            movement=movement,
            policy=policy,
        )
    except CaptureClaimUnverifiableError:
        verdict_value = VERDICT_AUDIT_REQUIRED
    else:
        matches = verdict_confirms_claim(verdict, claim.claim_kind)
        verdict_value = VERDICT_CONFIRM if matches else VERDICT_DENY

    commitment = seal_response(
        game_id=runtime.game_id,
        sub_game=runtime.sub_game,
        turn=claim.turn,
        responder_role=runtime.role.value,
        verdict=verdict_value,
        claim_id=claim.claim_id,
    )
    response = CaptureClaimResponse(
        claim_id=claim.claim_id,
        sub_game=claim.sub_game,
        turn=claim.turn,
        verdict=verdict_value,
        commitment=commitment,
    )
    runtime.responses[claim.claim_id] = response

    if runtime.audit is not None:
        runtime.audit.append(
            AuditEventType.CAPTURE_CLAIM_RESPONSE,
            response_payload(response, responder_role=runtime.role.value),
            turn_number=claim.turn,
        )
    # audit_required must never itself mark the claim confirmed -- only an
    # actual, self-verified confirm does.
    if verdict_value == VERDICT_CONFIRM:
        runtime.pending = True
    return response
