"""CAPTURE_CLAIM / CAPTURE_CLAIM_RESPONSE (E-21, E-22): cop is the
mandatory, sole initiator -- Correction 1. Split out of
``test_capture_claim.py`` purely to stay under the 150-line lecturer limit.

``claim_envelope``/``response_envelope`` are the shared envelope builders --
imported from here by ``test_capture_claim.py`` and
``test_capture_claim_freshness.py`` too, the same way
``tests/peer/test_orchestrator.py``'s ``drive_to_ready`` is shared."""

from __future__ import annotations

import pytest

from police_thief.domain.enums import Role
from police_thief.protocol.capture_claim import (
    CLAIM_KIND_BARRIER_ON_THIEF,
    VERDICT_AUDIT_REQUIRED,
    VERDICT_CONFIRM,
)
from police_thief.protocol.capture_claim_validation import (
    validate_claim_envelope,
    validate_response_envelope,
)
from police_thief.protocol.exceptions import (
    WrongReceiverRoleError,
    WrongSenderRoleError,
)
from police_thief.protocol.messages import MessageType, new_envelope


def claim_envelope(*, sender=Role.POLICE, receiver=Role.THIEF, turn=5, **overrides):
    payload = {
        "claim_id": "c1",
        "sub_game": 1,
        "claim_kind": CLAIM_KIND_BARRIER_ON_THIEF,
        "commitment": "a" * 64,
    }
    payload.update(overrides)
    return new_envelope(
        game_id="g1",
        sender_role=sender,
        receiver_role=receiver,
        message_type=MessageType.CAPTURE_CLAIM,
        payload=payload,
        turn_number=turn,
    )


def response_envelope(*, sender=Role.THIEF, receiver=Role.POLICE, turn=5, **overrides):
    payload = {
        "claim_id": "c1",
        "sub_game": 1,
        "verdict": VERDICT_CONFIRM,
        "commitment": "b" * 64,
    }
    payload.update(overrides)
    return new_envelope(
        game_id="g1",
        sender_role=sender,
        receiver_role=receiver,
        message_type=MessageType.CAPTURE_CLAIM_RESPONSE,
        payload=payload,
        turn_number=turn,
    )


def test_cop_initiated_claim_is_accepted():
    claim = validate_claim_envelope(claim_envelope())
    assert claim.claim_id == "c1"
    assert claim.claim_kind == CLAIM_KIND_BARRIER_ON_THIEF
    assert claim.turn == 5


def test_thief_sent_claim_is_rejected():
    envelope = claim_envelope(sender=Role.THIEF, receiver=Role.POLICE)
    with pytest.raises(WrongSenderRoleError, match="mandatory initiator"):
        validate_claim_envelope(envelope)


def test_claim_addressed_to_the_cop_is_rejected():
    """The receiver_role check, independent of who sent it."""
    envelope = claim_envelope(receiver=Role.POLICE)
    with pytest.raises(WrongReceiverRoleError):
        validate_claim_envelope(envelope)


def test_thief_sent_response_is_accepted():
    response = validate_response_envelope(response_envelope())
    assert response.verdict == VERDICT_CONFIRM


def test_cop_sent_response_is_rejected():
    envelope = response_envelope(sender=Role.POLICE, receiver=Role.THIEF)
    with pytest.raises(WrongSenderRoleError):
        validate_response_envelope(envelope)


def test_thief_sent_audit_required_response_is_accepted():
    """audit_required is a legitimate, role-valid response -- not malformed,
    not a confirm, not a deny."""
    envelope = response_envelope(verdict=VERDICT_AUDIT_REQUIRED)
    response = validate_response_envelope(envelope)
    assert response.verdict == VERDICT_AUDIT_REQUIRED
