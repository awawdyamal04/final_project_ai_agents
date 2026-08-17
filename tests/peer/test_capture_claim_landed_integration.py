"""Two-peer integration for the ``landed`` capture_claim ground (E-21, E-22):
real orchestrators, real ``LoopbackClient`` round trip. The cop claims a
landed capture without supplying ``movement`` (never available live); the
thief must answer ``audit_required`` -- never crash, never leak, never guess
-- and the game must remain able to finish (Final Reveal, mutual audit).

Split out of ``test_capture_claim_orchestrator.py`` purely to stay under the
150-line lecturer limit; reuses its ``_play_one_real_turn`` helper."""

from __future__ import annotations

from police_thief.domain.enums import CaptureReason
from police_thief.protocol.capture_claim import VERDICT_AUDIT_REQUIRED
from tests.peer.test_capture_claim_orchestrator import _play_one_real_turn


async def test_landed_claim_over_the_real_transport_is_audit_required(peer_pair):
    """No movement is ever supplied live -- the thief cannot self-verify a
    landed collision (E-8/E-9) -- so the real round trip must come back
    audit_required, not a crash and not a guessed confirm/deny."""
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)

    response = await cop.orchestrator.claim_capture(1, CaptureReason.COP_LANDED_ON_THIEF)

    assert response.verdict == VERDICT_AUDIT_REQUIRED
    assert not cop.orchestrator.capture_claims.pending
    assert not thief.orchestrator.capture_claims.pending


async def test_landed_claim_audit_required_still_reaches_final_reveal_and_audit(
    peer_pair,
):
    """Gameplay/termination stays safe and deterministic: an audit_required
    verdict never sets CLAIM_PENDING_AUDIT, and Final Reveal plus the mutual
    audit remain fully reachable afterward -- exactly like the no-claim and
    confirmed-claim paths."""
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)

    await cop.orchestrator.claim_capture(1, CaptureReason.COP_LANDED_ON_THIEF)
    assert not cop.orchestrator.capture_claims.pending

    cop_verified = await cop.orchestrator.send_final_reveal()
    thief_verified = await thief.orchestrator.send_final_reveal()

    assert cop_verified >= 1
    assert thief_verified >= 1
    assert cop.orchestrator.opponent_audit_received
    assert thief.orchestrator.opponent_audit_received
