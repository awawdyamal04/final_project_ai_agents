"""``find_claim_records``/``find_response_records`` (E-21, E-22): pulling
capture_claim events back out of a decoded log. Split out of
``test_capture_claim_records.py`` purely to stay under the 150-line
lecturer limit -- reuses that file's ``log`` fixture and ``a_claim``/
``a_response`` builders."""

from __future__ import annotations

from police_thief.audit.capture_claim_records import (
    claim_payload,
    find_claim_records,
    find_response_records,
    response_payload,
)
from police_thief.audit.records import AuditEventType
from police_thief.audit.verifier import load_records
from tests.audit.test_capture_claim_records import a_claim, a_response, log  # noqa: F401


def test_find_claim_records_returns_only_claims(log):  # noqa: F811
    log.append(AuditEventType.SUB_GAME_START, {})
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
    records = load_records(log.path)
    found = find_claim_records(records)
    assert len(found) == 1
    assert found[0]["event_type"] == AuditEventType.CAPTURE_CLAIM.value


def test_find_response_records_returns_only_responses(log):  # noqa: F811
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
    records = load_records(log.path)
    found = find_response_records(records)
    assert len(found) == 1
    assert found[0]["event_type"] == AuditEventType.CAPTURE_CLAIM_RESPONSE.value


def test_find_functions_return_empty_lists_when_absent(log):  # noqa: F811
    log.append(AuditEventType.SUB_GAME_START, {})
    records = load_records(log.path)
    assert find_claim_records(records) == []
    assert find_response_records(records) == []
