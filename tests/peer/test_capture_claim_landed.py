"""Live capture_claim runtime (E-21, E-22): the ``landed`` ground (cop lands
on the thief) and ``audit_required``.

``landed`` needs the cop's true position, which the thief structurally
cannot hold (E-8/E-9). ``handle_claim`` must never let
``CaptureClaimUnverifiableError`` escape and crash the peer or break the
game loop -- it is caught and mapped onto ``VERDICT_AUDIT_REQUIRED``: an
honest "cannot verify live", never a guessed confirm/deny, never a leak.

Split out of ``test_capture_claim_runtime.py`` purely to stay under the
150-line lecturer limit; reuses its ``claim_envelope`` helper."""

from __future__ import annotations

from police_thief.audit.records import AuditEventType
from police_thief.audit.verifier import load_records
from police_thief.audit.writer import AuditLog
from police_thief.domain.capture_claim import CLAIM_KIND_LANDED
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Role
from police_thief.domain.simultaneity import TurnMovement
from police_thief.domain.state import LocalState
from police_thief.peer.capture_claim_runtime import CaptureClaimRuntime
from police_thief.peer.capture_claim_thief import handle_claim
from police_thief.protocol.capture_claim import VERDICT_AUDIT_REQUIRED, VERDICT_CONFIRM
from tests.domain.conftest import place_at
from tests.peer.test_capture_claim_runtime import claim_envelope


def _thief_runtime() -> CaptureClaimRuntime:
    return CaptureClaimRuntime(game_id="g1", role=Role.THIEF)


def _thief_state(shared) -> LocalState:
    return place_at(LocalState.initial(Role.THIEF, shared), 3, 3)


def test_landed_claim_confirmed_when_movement_is_supplied(shared):
    mv = TurnMovement(
        cop_before=Coordinate(3, 2), cop_after=Coordinate(3, 3),
        thief_before=Coordinate(3, 3), thief_after=Coordinate(3, 3),
    )
    response = handle_claim(
        _thief_runtime(), claim_envelope(claim_kind=CLAIM_KIND_LANDED),
        thief_state=_thief_state(shared), config=shared,
        latest_completed_turn=5, movement=mv,
    )
    assert response.verdict == VERDICT_CONFIRM


def test_landed_claim_without_movement_does_not_raise_out_of_the_handler(shared):
    """The core requirement: this must never crash the peer or the game loop."""
    response = handle_claim(
        _thief_runtime(), claim_envelope(claim_kind=CLAIM_KIND_LANDED),
        thief_state=_thief_state(shared), config=shared, latest_completed_turn=5,
    )
    assert response is not None


def test_landed_claim_without_movement_is_audit_required(shared):
    response = handle_claim(
        _thief_runtime(), claim_envelope(claim_kind=CLAIM_KIND_LANDED),
        thief_state=_thief_state(shared), config=shared, latest_completed_turn=5,
    )
    assert response.verdict == VERDICT_AUDIT_REQUIRED


def test_audit_required_does_not_set_pending(shared):
    runtime = _thief_runtime()
    handle_claim(
        runtime, claim_envelope(claim_kind=CLAIM_KIND_LANDED),
        thief_state=_thief_state(shared), config=shared, latest_completed_turn=5,
    )
    assert not runtime.pending


def test_audit_required_response_carries_no_coordinate_or_nonce(shared):
    response = handle_claim(
        _thief_runtime(), claim_envelope(claim_kind=CLAIM_KIND_LANDED),
        thief_state=_thief_state(shared), config=shared, latest_completed_turn=5,
    )
    payload = response.to_payload()
    for banned in ("cell", "position", "coordinate", "nonce", "row", "col"):
        assert banned not in payload


def test_audit_required_response_is_audit_logged(shared, tmp_path):
    log = AuditLog(path=tmp_path / "thief.jsonl", game_id="g1", role="thief")
    runtime = _thief_runtime()
    runtime.audit = log
    handle_claim(
        runtime, claim_envelope(claim_kind=CLAIM_KIND_LANDED),
        thief_state=_thief_state(shared), config=shared, latest_completed_turn=5,
    )
    records = load_records(log.path)
    assert records[0]["event_type"] == AuditEventType.CAPTURE_CLAIM_RESPONSE.value
    assert records[0]["payload"]["verdict"] == VERDICT_AUDIT_REQUIRED
