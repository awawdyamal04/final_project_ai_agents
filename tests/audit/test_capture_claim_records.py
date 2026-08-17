"""Audit-record payload shaping for capture_claim (E-21, E-22): claim and
response both land in the append-only, hash-chained log (requirement 4), and
carry no coordinate, cell, or nonce (E-9, E-18).

``find_claim_records``/``find_response_records`` are tested in
``test_capture_claim_records_lookup.py`` (importing ``log``/``a_claim``/
``a_response`` from here) -- split purely to stay under the 150-line
lecturer limit."""

from __future__ import annotations

import pytest

from police_thief.audit.capture_claim_records import claim_payload, response_payload
from police_thief.audit.exceptions import AuditPrivacyError
from police_thief.audit.records import AuditEventType
from police_thief.audit.verifier import load_records
from police_thief.audit.writer import AuditLog
from police_thief.protocol.capture_claim import CaptureClaim, CaptureClaimResponse


@pytest.fixture
def log(tmp_path) -> AuditLog:
    return AuditLog(path=tmp_path / "audit.jsonl", game_id="g1", role="police")


def a_claim() -> CaptureClaim:
    return CaptureClaim(
        claim_id="c1", sub_game=1, turn=5,
        claim_kind="barrier_on_thief", commitment="a" * 64,
    )


def a_response(verdict: str = "confirm") -> CaptureClaimResponse:
    return CaptureClaimResponse(
        claim_id="c1", sub_game=1, turn=5, verdict=verdict, commitment="b" * 64,
    )


# ----------------------------------------------------------------------
# Payload shaping
# ----------------------------------------------------------------------


def test_claim_payload_adds_the_claimant_role():
    payload = claim_payload(a_claim(), claimant_role="police")
    assert payload["claimant_role"] == "police"
    assert payload["claim_id"] == "c1"
    assert payload["claim_kind"] == "barrier_on_thief"


def test_response_payload_adds_the_responder_role():
    payload = response_payload(a_response(), responder_role="thief")
    assert payload["responder_role"] == "thief"
    assert payload["verdict"] == "confirm"


def test_shaped_payloads_carry_no_coordinate_cell_or_nonce():
    for payload in (
        claim_payload(a_claim(), claimant_role="police"),
        response_payload(a_response(), responder_role="thief"),
    ):
        for banned in ("cell", "position", "coordinate", "nonce", "row", "col"):
            assert banned not in payload


# ----------------------------------------------------------------------
# Both event types actually reach the append-only chain (requirement 4)
# ----------------------------------------------------------------------


def test_claim_is_appended_to_the_hash_chained_log(log):
    record = log.append(
        AuditEventType.CAPTURE_CLAIM,
        claim_payload(a_claim(), claimant_role="police"),
        turn_number=5,
    )
    assert record.event_type == AuditEventType.CAPTURE_CLAIM.value
    assert record.turn_number == 5
    on_disk = load_records(log.path)
    assert on_disk[0]["current_event_hash"] == record.current_event_hash


def test_response_is_appended_to_the_hash_chained_log(log):
    record = log.append(
        AuditEventType.CAPTURE_CLAIM_RESPONSE,
        response_payload(a_response(), responder_role="thief"),
        turn_number=5,
    )
    assert record.event_type == AuditEventType.CAPTURE_CLAIM_RESPONSE.value


def test_capture_claim_events_do_not_trip_the_nonce_privacy_guard(log):
    """Neither payload carries a nonce, so the pre-final-reveal privacy
    schedule (E-18) never rejects them."""
    log.append(
        AuditEventType.CAPTURE_CLAIM,
        claim_payload(a_claim(), claimant_role="police"),
        turn_number=5,
    )
    log.append(
        AuditEventType.CAPTURE_CLAIM_RESPONSE,
        response_payload(a_response(), responder_role="thief"),
        turn_number=5,
    )
    text = log.path.read_text(encoding="utf-8")
    assert "nonce" not in text


def test_global_state_keys_are_still_refused_even_via_this_path(log):
    """The generic ``AuditLog`` privacy guard still applies -- this module
    does not bypass it."""
    with pytest.raises(AuditPrivacyError):
        log.append(
            AuditEventType.CAPTURE_CLAIM,
            {**claim_payload(a_claim(), claimant_role="police"),
             "thief_position": "leaked"},
            turn_number=5,
        )
