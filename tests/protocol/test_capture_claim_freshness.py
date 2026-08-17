"""CAPTURE_CLAIM / CAPTURE_CLAIM_RESPONSE (E-21, E-22): malformed payloads
and stale/future claims are rejected. Split out of ``test_capture_claim.py``
purely to stay under the 150-line lecturer limit."""

from __future__ import annotations

import pytest

from police_thief.domain.enums import Role
from police_thief.protocol.capture_claim_validation import (
    validate_claim_envelope,
    validate_claim_freshness,
    validate_response_envelope,
)
from police_thief.protocol.exceptions import (
    FutureTurnError,
    ProtocolValidationError,
    StaleTurnError,
)
from police_thief.protocol.messages import MessageType, new_envelope
from tests.protocol.test_capture_claim_roles import claim_envelope, response_envelope


def test_unknown_claim_kind_is_rejected():
    with pytest.raises(ProtocolValidationError, match="claim_kind"):
        validate_claim_envelope(claim_envelope(claim_kind="teleport"))


def test_empty_claim_id_is_rejected():
    with pytest.raises(ProtocolValidationError, match="claim_id"):
        validate_claim_envelope(claim_envelope(claim_id=""))


def test_missing_turn_number_is_rejected():
    with pytest.raises(ProtocolValidationError, match="turn_number"):
        validate_claim_envelope(claim_envelope(turn=None))


def test_unknown_verdict_is_rejected():
    with pytest.raises(ProtocolValidationError, match="verdict"):
        validate_response_envelope(response_envelope(verdict="maybe"))


def test_empty_response_claim_id_is_rejected():
    with pytest.raises(ProtocolValidationError, match="claim_id"):
        validate_response_envelope(response_envelope(claim_id=""))


def test_unknown_payload_field_is_rejected_by_the_envelope_schema():
    with pytest.raises(ProtocolValidationError, match="unknown payload field"):
        claim_envelope(sneaky=1)


def test_missing_payload_field_is_rejected_by_the_envelope_schema():
    with pytest.raises(ProtocolValidationError, match="missing payload field"):
        new_envelope(
            game_id="g1",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.CAPTURE_CLAIM,
            payload={"claim_id": "c1", "sub_game": 1, "claim_kind": "landed"},
            turn_number=5,
        )


def test_claim_for_the_just_completed_turn_is_fresh():
    validate_claim_freshness(claim_turn=5, latest_completed_turn=5)


def test_claim_for_an_old_turn_is_stale():
    with pytest.raises(StaleTurnError):
        validate_claim_freshness(claim_turn=3, latest_completed_turn=5)


def test_claim_for_a_turn_not_yet_completed_is_future():
    with pytest.raises(FutureTurnError):
        validate_claim_freshness(claim_turn=8, latest_completed_turn=5)
