"""Live capture_claim runtime (E-21, E-22): the cop-side builder/acceptor
(``CaptureClaimRuntime.build_claim``/``record_response``), below the full
orchestrator -- exercises message handling directly with hand-built
envelopes, the way ``tests/protocol`` and ``tests/crypto`` test their own
layers below the orchestrator.

The thief-side ``handle_claim`` answerer is tested in
``test_capture_claim_thief_handler.py`` (barrier/no_legal_move/roles/
freshness) and ``test_capture_claim_landed.py`` (the ``landed`` ground and
``audit_required``) -- both import ``claim_envelope``/``response_envelope``
from here. Split purely to stay under the 150-line lecturer limit, which
applies to test files too."""

from __future__ import annotations

import pytest

from police_thief.audit.records import AuditEventType
from police_thief.audit.verifier import load_records
from police_thief.audit.writer import AuditLog
from police_thief.domain.enums import CaptureReason, Role
from police_thief.peer.capture_claim_runtime import CaptureClaimRuntime
from police_thief.protocol.capture_claim import VERDICT_CONFIRM, VERDICT_DENY
from police_thief.protocol.exceptions import WrongSenderRoleError
from police_thief.protocol.messages import MessageType, new_envelope


def claim_envelope(
    *, turn=5, sender=Role.POLICE, claim_id="c1", claim_kind="barrier_on_thief"
):
    return new_envelope(
        game_id="g1",
        sender_role=sender,
        receiver_role=Role.THIEF,
        message_type=MessageType.CAPTURE_CLAIM,
        payload={
            "claim_id": claim_id, "sub_game": 1,
            "claim_kind": claim_kind, "commitment": "a" * 64,
        },
        turn_number=turn,
    )


def response_envelope(*, sender=Role.THIEF, verdict=VERDICT_CONFIRM, claim_id="c1"):
    receiver = Role.POLICE if sender is Role.THIEF else Role.THIEF
    return new_envelope(
        game_id="g1", sender_role=sender, receiver_role=receiver,
        message_type=MessageType.CAPTURE_CLAIM_RESPONSE,
        payload={"claim_id": claim_id, "sub_game": 1, "verdict": verdict,
                  "commitment": "b" * 64},
        turn_number=5,
    )


# ----------------------------------------------------------------------
# Cop side: CaptureClaimRuntime.build_claim / record_response
# ----------------------------------------------------------------------


def test_build_claim_returns_correctly_shaped_claim():
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE)
    claim = runtime.build_claim(turn=5, reason=CaptureReason.BARRIER_ON_THIEF)
    assert claim.turn == 5
    assert claim.claim_kind == "barrier_on_thief"
    assert len(claim.commitment) == 64


def test_build_claim_appends_to_audit_when_present(tmp_path):
    log = AuditLog(path=tmp_path / "cop.jsonl", game_id="g1", role="police")
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE, audit=log)
    runtime.build_claim(turn=5, reason=CaptureReason.BARRIER_ON_THIEF)
    records = load_records(log.path)
    assert records[0]["event_type"] == AuditEventType.CAPTURE_CLAIM.value
    assert records[0]["payload"]["claimant_role"] == "police"


def test_build_claim_without_audit_does_not_error():
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE, audit=None)
    runtime.build_claim(turn=5, reason=CaptureReason.BARRIER_ON_THIEF)  # no raise


def test_record_response_accepts_a_thief_sent_response():
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE)
    response = runtime.record_response(response_envelope())
    assert response.verdict == VERDICT_CONFIRM


def test_record_response_sets_pending_on_confirm():
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE)
    assert not runtime.pending
    runtime.record_response(response_envelope(verdict=VERDICT_CONFIRM))
    assert runtime.pending


def test_record_response_does_not_set_pending_on_deny():
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE)
    runtime.record_response(response_envelope(verdict=VERDICT_DENY))
    assert not runtime.pending


def test_record_response_rejects_a_cop_sent_response():
    runtime = CaptureClaimRuntime(game_id="g1", role=Role.POLICE)
    with pytest.raises(WrongSenderRoleError):
        runtime.record_response(response_envelope(sender=Role.POLICE))
