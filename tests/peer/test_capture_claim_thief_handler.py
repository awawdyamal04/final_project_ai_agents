"""Live capture_claim runtime (E-21, E-22): the thief-side answerer
(``handle_claim``) for the two self-sufficient grounds -- ``barrier_on_thief``
and ``no_legal_move`` -- plus role/freshness/idempotency/audit-logging. The
``landed`` ground and ``audit_required`` live in
``test_capture_claim_landed.py`` -- split purely to stay under the 150-line
lecturer limit.

Reuses ``claim_envelope``/``response_envelope`` from
``test_capture_claim_runtime.py``."""

from __future__ import annotations

import pytest

from police_thief.audit.records import AuditEventType
from police_thief.audit.verifier import load_records
from police_thief.audit.writer import AuditLog
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Role
from police_thief.domain.state import LocalState
from police_thief.peer.capture_claim_runtime import CaptureClaimRuntime
from police_thief.peer.capture_claim_thief import handle_claim
from police_thief.protocol.capture_claim import VERDICT_CONFIRM, VERDICT_DENY
from police_thief.protocol.exceptions import (
    FutureTurnError,
    StaleTurnError,
    WrongSenderRoleError,
)
from tests.domain.conftest import place_at, wall_in
from tests.peer.test_capture_claim_runtime import claim_envelope


@pytest.fixture
def thief_runtime():
    return CaptureClaimRuntime(game_id="g1", role=Role.THIEF)


@pytest.fixture
def thief_state(shared) -> LocalState:
    return place_at(LocalState.initial(Role.THIEF, shared), 3, 3)


def test_thief_confirms_a_true_barrier_claim(thief_runtime, thief_state, shared):
    response = handle_claim(
        thief_runtime, claim_envelope(claim_kind="barrier_on_thief"),
        thief_state=thief_state, config=shared,
        latest_completed_turn=5, barrier_cell=Coordinate(3, 3),
    )
    assert response.verdict == VERDICT_CONFIRM
    assert thief_runtime.pending


def test_thief_denies_a_false_barrier_claim(thief_runtime, thief_state, shared):
    response = handle_claim(
        thief_runtime, claim_envelope(claim_kind="barrier_on_thief"),
        thief_state=thief_state, config=shared,
        latest_completed_turn=5, barrier_cell=Coordinate(0, 0),
    )
    assert response.verdict == VERDICT_DENY
    assert not thief_runtime.pending


def test_thief_confirms_a_true_no_legal_move_claim(thief_runtime, shared):
    trapped = wall_in(
        place_at(LocalState.initial(Role.THIEF, shared), 3, 3),
        [(2, 3), (4, 3), (3, 4), (3, 2)],
    )
    response = handle_claim(
        thief_runtime, claim_envelope(claim_kind="no_legal_move"),
        thief_state=trapped, config=shared, latest_completed_turn=5,
    )
    assert response.verdict == VERDICT_CONFIRM


def test_thief_initiated_claim_is_rejected(thief_runtime, thief_state, shared):
    with pytest.raises(WrongSenderRoleError):
        handle_claim(
            thief_runtime,
            claim_envelope(sender=Role.THIEF, claim_kind="barrier_on_thief"),
            thief_state=thief_state, config=shared, latest_completed_turn=5,
        )


def test_stale_claim_is_rejected(thief_runtime, thief_state, shared):
    with pytest.raises(StaleTurnError):
        handle_claim(
            thief_runtime, claim_envelope(turn=2),
            thief_state=thief_state, config=shared, latest_completed_turn=5,
        )


def test_future_claim_is_rejected(thief_runtime, thief_state, shared):
    with pytest.raises(FutureTurnError):
        handle_claim(
            thief_runtime, claim_envelope(turn=9),
            thief_state=thief_state, config=shared, latest_completed_turn=5,
        )


def test_duplicate_claim_id_is_answered_idempotently(
    thief_runtime, thief_state, shared, tmp_path
):
    """A retried CAPTURE_CLAIM (same claim_id) returns the cached response
    rather than recomputing -- and, critically, does not append a second
    audit record."""
    log = AuditLog(path=tmp_path / "thief.jsonl", game_id="g1", role="thief")
    thief_runtime.audit = log
    envelope = claim_envelope(claim_id="dup-1")
    first = handle_claim(
        thief_runtime, envelope, thief_state=thief_state, config=shared,
        latest_completed_turn=5, barrier_cell=Coordinate(3, 3),
    )
    second = handle_claim(
        thief_runtime, envelope, thief_state=thief_state, config=shared,
        latest_completed_turn=5, barrier_cell=Coordinate(3, 3),
    )
    assert first == second
    responses_logged = [
        r for r in load_records(log.path)
        if r["event_type"] == AuditEventType.CAPTURE_CLAIM_RESPONSE.value
    ]
    assert len(responses_logged) == 1


def test_response_is_appended_to_the_thief_own_audit_log(
    thief_runtime, thief_state, shared, tmp_path
):
    log = AuditLog(path=tmp_path / "thief.jsonl", game_id="g1", role="thief")
    thief_runtime.audit = log
    handle_claim(
        thief_runtime, claim_envelope(claim_kind="barrier_on_thief"),
        thief_state=thief_state, config=shared,
        latest_completed_turn=5, barrier_cell=Coordinate(3, 3),
    )
    records = load_records(log.path)
    assert records[0]["event_type"] == AuditEventType.CAPTURE_CLAIM_RESPONSE.value
    assert records[0]["payload"]["responder_role"] == "thief"
