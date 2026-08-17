"""Replay-time capture_claim check (E-21, E-22): does the independently
recomputed terminal condition agree with what was claimed and answered live?
Direct unit tests of ``check_capture_claims``, below the full replay
pipeline.

D-41 augmented, not replaced -- a sub_game with no claims at all must be
unaffected. Full-pipeline tests (``replay_logs`` end to end, and the
``landed``/``audit_required`` ground specifically) are split into
``test_capture_claim_check_pipeline.py`` and
``test_capture_claim_check_landed.py`` -- both reuse ``claim_record``/
``response_record`` from here -- purely to stay under the 150-line lecturer
limit, which applies to test files too."""

from __future__ import annotations

from police_thief.audit.capture_claim_records import claim_payload, response_payload
from police_thief.audit.records import AuditEventType
from police_thief.domain.enums import CaptureReason
from police_thief.domain.terminal import capture as terminal_capture
from police_thief.protocol.capture_claim import (
    VERDICT_CONFIRM,
    VERDICT_DENY,
    CaptureClaim,
    CaptureClaimResponse,
)
from police_thief.replay.capture_claim_check import check_capture_claims


def claim_record(*, turn=5, claim_id="c1", claim_kind="barrier_on_thief"):
    claim = CaptureClaim(
        claim_id=claim_id, sub_game=1, turn=turn,
        claim_kind=claim_kind, commitment="a" * 64,
    )
    return {
        "event_type": AuditEventType.CAPTURE_CLAIM.value,
        "turn_number": turn,
        "payload": claim_payload(claim, claimant_role="police"),
    }


def response_record(*, verdict=VERDICT_CONFIRM, claim_id="c1"):
    response = CaptureClaimResponse(
        claim_id=claim_id, sub_game=1, turn=5, verdict=verdict, commitment="b" * 64,
    )
    return {
        "event_type": AuditEventType.CAPTURE_CLAIM_RESPONSE.value,
        "turn_number": 5,
        "payload": response_payload(response, responder_role="thief"),
    }


def test_no_claims_yields_no_disagreements():
    assert check_capture_claims([], [], terminal=None) == []


def test_confirmed_claim_matching_the_reconstruction_agrees():
    terminal = terminal_capture(5, CaptureReason.BARRIER_ON_THIEF)
    disagreements = check_capture_claims(
        [claim_record()], [response_record(verdict=VERDICT_CONFIRM)], terminal
    )
    assert disagreements == []


def test_confirmed_claim_contradicted_by_the_reconstruction_is_flagged():
    """A false cop claim the thief wrongly (or collusively) confirmed."""
    terminal = terminal_capture(5, CaptureReason.THIEF_HAS_NO_LEGAL_MOVE)
    disagreements = check_capture_claims(
        [claim_record(claim_kind="barrier_on_thief")],
        [response_record(verdict=VERDICT_CONFIRM)],
        terminal,
    )
    assert len(disagreements) == 1
    assert "c1" in disagreements[0]


def test_confirmed_claim_when_no_capture_happened_at_all_is_flagged():
    disagreements = check_capture_claims(
        [claim_record()], [response_record(verdict=VERDICT_CONFIRM)], terminal=None
    )
    assert len(disagreements) == 1


def test_denied_claim_that_was_actually_true_is_flagged():
    """A false thief denial -- exactly what live evidence exists to catch."""
    terminal = terminal_capture(5, CaptureReason.BARRIER_ON_THIEF)
    disagreements = check_capture_claims(
        [claim_record()], [response_record(verdict=VERDICT_DENY)], terminal
    )
    assert len(disagreements) == 1
    assert "denied" in disagreements[0]


def test_denied_claim_that_was_correctly_false_agrees():
    disagreements = check_capture_claims(
        [claim_record()], [response_record(verdict=VERDICT_DENY)], terminal=None
    )
    assert disagreements == []


def test_claim_without_any_logged_response_is_flagged():
    disagreements = check_capture_claims([claim_record()], [], terminal=None)
    assert len(disagreements) == 1
    assert "never answered" in disagreements[0]


def test_a_claim_logged_in_both_peers_logs_is_checked_only_once():
    """Defensive de-duplication by claim_id."""
    terminal = terminal_capture(5, CaptureReason.BARRIER_ON_THIEF)
    disagreements = check_capture_claims(
        [claim_record(), claim_record()],  # same claim_id in "both logs"
        [response_record(verdict=VERDICT_CONFIRM)],
        terminal,
    )
    assert disagreements == []  # agrees, and only checked once


def test_multiple_independent_claims_are_each_checked():
    terminal = terminal_capture(7, CaptureReason.BARRIER_ON_THIEF)
    disagreements = check_capture_claims(
        [claim_record(turn=5, claim_id="c1"), claim_record(turn=7, claim_id="c2")],
        [
            response_record(claim_id="c1", verdict=VERDICT_CONFIRM),  # turn 5, wrong
            response_record(claim_id="c2", verdict=VERDICT_CONFIRM),  # turn 7, right
        ],
        terminal,
    )
    assert len(disagreements) == 1
    assert "c1" in disagreements[0]
