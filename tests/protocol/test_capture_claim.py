"""CAPTURE_CLAIM / CAPTURE_CLAIM_RESPONSE (E-21, E-22): schema shape. No
coordinate, no cell, no nonce ever appears here -- prd.md Sec 14.6/14.7.

Role validation lives in ``test_capture_claim_roles.py``; malformed-payload
and freshness rejection live in ``test_capture_claim_freshness.py`` -- split
purely to stay under the 150-line lecturer limit, which applies to test
files too."""

from __future__ import annotations

from police_thief.domain.enums import CaptureReason
from police_thief.protocol.capture_claim import (
    CLAIM_KIND_BARRIER_ON_THIEF,
    CLAIM_KIND_LANDED,
    CLAIM_KIND_NO_LEGAL_MOVE,
    CLAIM_KINDS,
    VERDICT_AUDIT_REQUIRED,
    VERDICT_CONFIRM,
    VERDICT_DENY,
    VERDICTS,
    CaptureClaim,
    CaptureClaimResponse,
    claim_kind_for_reason,
    reason_for_claim_kind,
)
from tests.protocol.test_capture_claim_roles import claim_envelope


def test_claim_kind_vocabulary_maps_onto_capture_reason():
    for reason in (
        CaptureReason.COP_LANDED_ON_THIEF,
        CaptureReason.BARRIER_ON_THIEF,
        CaptureReason.THIEF_HAS_NO_LEGAL_MOVE,
    ):
        kind = claim_kind_for_reason(reason)
        assert kind in CLAIM_KINDS
        assert reason_for_claim_kind(kind) is reason


def test_claim_kinds_are_exactly_the_three_grounds():
    assert {
        CLAIM_KIND_LANDED, CLAIM_KIND_BARRIER_ON_THIEF, CLAIM_KIND_NO_LEGAL_MOVE,
    } == CLAIM_KINDS


def test_verdicts_are_confirm_deny_or_audit_required_only():
    assert {VERDICT_CONFIRM, VERDICT_DENY, VERDICT_AUDIT_REQUIRED} == VERDICTS


def test_claim_payload_carries_no_coordinate_cell_or_nonce():
    claim = CaptureClaim(
        claim_id="c1", sub_game=1, turn=5,
        claim_kind=CLAIM_KIND_LANDED, commitment="a" * 64,
    )
    payload = claim.to_payload()
    for banned in ("cell", "position", "coordinate", "nonce", "row", "col"):
        assert banned not in payload


def test_response_payload_carries_no_coordinate_cell_or_nonce():
    for verdict in (VERDICT_CONFIRM, VERDICT_DENY, VERDICT_AUDIT_REQUIRED):
        response = CaptureClaimResponse(
            claim_id="c1", sub_game=1, turn=5,
            verdict=verdict, commitment="b" * 64,
        )
        payload = response.to_payload()
        for banned in ("cell", "position", "coordinate", "nonce", "row", "col"):
            assert banned not in payload


def test_claim_envelope_round_trips_through_the_wire():
    from police_thief.protocol.codec import decode_envelope, encode_envelope

    original = claim_envelope()
    restored = decode_envelope(encode_envelope(original))
    assert restored == original
