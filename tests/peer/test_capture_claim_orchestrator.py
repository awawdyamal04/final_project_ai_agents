"""Two-peer integration for capture_claim (E-21, E-22): real orchestrators,
real ``LoopbackClient`` round trips, real commit-reveal turns -- only the
final capture scenario is forced directly onto ``LocalState`` (constructing
an actual barrier-walled or landed position through real play is
strategy-dependent and not what this test is about)."""

from __future__ import annotations

import asyncio

import pytest

from police_thief.domain.actions import PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason
from police_thief.protocol.capture_claim import VERDICT_CONFIRM, VERDICT_DENY
from tests.domain.conftest import place_at, wall_in
from tests.peer.test_orchestrator import drive_to_ready


async def _play_one_real_turn(cop, thief):
    """One genuine commit-reveal turn, so both sides have a completed turn
    to attach the claim's freshness check to (turn 1)."""
    await drive_to_ready(cop, thief)
    await asyncio.gather(
        cop.orchestrator.play_turn(1), thief.orchestrator.play_turn(1)
    )


# ----------------------------------------------------------------------
# Cop initiates, thief confirms/denies -- over the real loopback transport
# ----------------------------------------------------------------------


async def test_cop_initiates_and_thief_confirms_a_true_claim(peer_pair):
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)

    # Force a genuine trapped position onto the thief's own true state --
    # the claim/response plumbing is what is under test here, not the
    # physics that would ordinarily produce this position over many turns.
    thief.orchestrator.state = wall_in(
        place_at(thief.orchestrator.state, 3, 3),
        [(2, 3), (4, 3), (3, 4), (3, 2)],
    )

    response = await cop.orchestrator.claim_capture(
        1, CaptureReason.THIEF_HAS_NO_LEGAL_MOVE
    )
    assert response.verdict == VERDICT_CONFIRM
    assert cop.orchestrator.capture_claims.pending
    assert thief.orchestrator.capture_claims.pending


async def test_cop_initiates_and_thief_denies_a_false_claim(peer_pair):
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)
    # Thief's true state is left alone -- open board, nothing trapped.

    response = await cop.orchestrator.claim_capture(
        1, CaptureReason.THIEF_HAS_NO_LEGAL_MOVE
    )
    assert response.verdict == VERDICT_DENY
    assert not cop.orchestrator.capture_claims.pending
    assert not thief.orchestrator.capture_claims.pending


async def test_barrier_on_thief_claim_uses_the_publicly_revealed_barrier(peer_pair):
    """barrier_cell comes from ``last_opponent_action`` (set by ``_on_reveal``
    from the cop's own revealed action) -- public, not reconstructed."""
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)

    thief.orchestrator.state = place_at(thief.orchestrator.state, 5, 5)
    thief.orchestrator.last_opponent_action = PlaceBarrier(Coordinate(5, 5))

    response = await cop.orchestrator.claim_capture(1, CaptureReason.BARRIER_ON_THIEF)
    assert response.verdict == VERDICT_CONFIRM


# ----------------------------------------------------------------------
# Wrong-sender rejection, end to end (not just at the validation layer)
# ----------------------------------------------------------------------


async def test_thief_sent_claim_is_rejected_over_the_real_transport(peer_pair):
    """The thief has no ``claim_capture`` call site in real use (Correction
    1); calling the same method the wrong side proves the rejection is
    enforced by the protocol, not merely by which method call sites exist."""
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)

    with pytest.raises(Exception) as excinfo:
        await thief.orchestrator.claim_capture(1, CaptureReason.BARRIER_ON_THIEF)
    # The rejection happens on the cop's side (receiver), surfaces to the
    # thief-side caller as its reply being rejected.
    assert "rejected" in str(excinfo.value) or "sender" in str(excinfo.value).lower()


# ----------------------------------------------------------------------
# CLAIM_PENDING_AUDIT: confirmed claim stops turns, audit still runs
# ----------------------------------------------------------------------


async def test_confirmed_claim_does_not_block_final_reveal_or_mutual_audit(peer_pair):
    """Requirement 5: CLAIM_PENDING_AUDIT stops new turns (peer/run.py's
    loop), but Final Reveal and the mutual audit are unconditional and must
    still complete once a claim is confirmed."""
    cop, thief = peer_pair
    await _play_one_real_turn(cop, thief)

    thief.orchestrator.state = wall_in(
        place_at(thief.orchestrator.state, 3, 3),
        [(2, 3), (4, 3), (3, 4), (3, 2)],
    )
    await cop.orchestrator.claim_capture(1, CaptureReason.THIEF_HAS_NO_LEGAL_MOVE)
    assert cop.orchestrator.capture_claims.pending

    cop_verified = await cop.orchestrator.send_final_reveal()
    thief_verified = await thief.orchestrator.send_final_reveal()

    assert cop_verified >= 1
    assert thief_verified >= 1
    assert cop.orchestrator.opponent_audit_received
    assert thief.orchestrator.opponent_audit_received
