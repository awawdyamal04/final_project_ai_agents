"""One turn of tolerance for a peer running slightly ahead (Q-20)."""

from __future__ import annotations

import pytest

from police_thief.crypto.exceptions import (
    FutureTurnMessageError,
    StaleTurnMessageError,
)
from police_thief.domain.actions import Move
from police_thief.domain.enums import Direction, Role
from police_thief.peer.pending import (
    MAX_TURNS_AHEAD,
    BufferOverflowError,
    PendingTurnBuffer,
)
from police_thief.protocol.exceptions import ConflictingDuplicateError
from police_thief.protocol.messages import MessageType, new_envelope
from tests.peer.test_crypto_turn import play_together
from tests.peer.test_orchestrator import drive_to_ready


def commit_envelope(turn: int, commitment: str = "a" * 64, mid: str = "m1"):
    return new_envelope(
        game_id="test-game",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.COMMIT,
        payload={"commitment": commitment, "commitment_schema": "v1"},
        turn_number=turn,
        message_id=mid,
    )


# ----------------------------------------------------------------------
# The buffer itself
# ----------------------------------------------------------------------


def test_buffer_holds_and_returns_in_deterministic_order():
    """Both peers must drain a turn's messages in the same order or diverge."""
    buffer = PendingTurnBuffer(10)
    reveal = new_envelope(
        game_id="g", sender_role=Role.POLICE, receiver_role=Role.THIEF,
        message_type=MessageType.REVEAL,
        payload={"sealed": {"v": 1}}, turn_number=2, message_id="r",
    )
    buffer.add(reveal, {"ok": True})
    buffer.add(commit_envelope(2, mid="c"), {"ok": True})

    drained = buffer.take_for_turn(2)
    assert [m.envelope.message_type for m in drained] == [
        MessageType.COMMIT,
        MessageType.REVEAL,
    ]
    assert len(buffer) == 0


def test_only_the_requested_turn_is_drained():
    buffer = PendingTurnBuffer(10)
    buffer.add(commit_envelope(2, mid="a"), {"ok": True})
    buffer.add(commit_envelope(3, mid="b"), {"ok": True})
    assert len(buffer.take_for_turn(2)) == 1
    assert buffer.turns_held() == (3,)


def test_exact_retry_returns_the_same_acknowledgement():
    buffer = PendingTurnBuffer(10)
    envelope = commit_envelope(2)
    buffer.add(envelope, {"ok": True, "n": 1})
    hit = buffer.lookup("m1", envelope.payload)
    assert hit is not None and hit.response == {"ok": True, "n": 1}


def test_retry_with_reordered_payload_keys_is_still_the_same_message():
    buffer = PendingTurnBuffer(10)
    envelope = new_envelope(
        game_id="g", sender_role=Role.POLICE, receiver_role=Role.THIEF,
        message_type=MessageType.CONFIG_REJECTED,
        payload={"reason": "x", "our_config_sha256": "a", "their_config_sha256": "b"},
        message_id="m", turn_number=2,
    )
    buffer.add(envelope, {"ok": True})
    assert buffer.lookup(
        "m",
        {"their_config_sha256": "b", "our_config_sha256": "a", "reason": "x"},
    ) is not None


def test_conflicting_retry_is_rejected():
    buffer = PendingTurnBuffer(10)
    buffer.add(commit_envelope(2, commitment="a" * 64), {"ok": True})
    with pytest.raises(ConflictingDuplicateError, match="different payload"):
        buffer.lookup("m1", {"commitment": "b" * 64, "commitment_schema": "v1"})


def test_buffer_overflow_is_refused():
    buffer = PendingTurnBuffer(2)
    buffer.add(commit_envelope(2, mid="a"), {"ok": True})
    buffer.add(commit_envelope(2, mid="b"), {"ok": True})
    with pytest.raises(BufferOverflowError, match="full"):
        buffer.add(commit_envelope(2, mid="c"), {"ok": True})
    assert buffer.overflows == 1


def test_clear_empties_the_buffer():
    buffer = PendingTurnBuffer(5)
    buffer.add(commit_envelope(2), {"ok": True})
    assert buffer.clear() == 1
    assert len(buffer) == 0


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        PendingTurnBuffer(0)


# ----------------------------------------------------------------------
# Orchestrator behaviour
# ----------------------------------------------------------------------


async def mid_turn(cop, thief, turn: int):
    """Leave the thief part-way through ``turn``.

    This is where the race actually bites. *Between* turns the next turn is
    already the expected one and needs no buffering -- the problem arises only
    when the opponent has finished a turn we are still working on.
    """
    await drive_to_ready(cop, thief)
    for played in range(1, turn):
        await play_together(cop, thief, played, Move(Direction.STAY), Move(Direction.STAY))
    thief.orchestrator.crypto.begin_turn(turn)
    assert thief.orchestrator.crypto.current.turn == turn


async def advance_to(thief, turn: int):
    """Move the thief on to ``turn``, as completing a turn would."""
    thief.orchestrator.crypto.abandon_turn("test advance")
    thief.orchestrator.crypto.begin_turn(turn)


async def test_next_turn_commit_is_buffered_not_rejected(peer_pair):
    """The race itself: a commit for turn 2 while we are still on turn 1."""
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    early = commit_envelope(3, mid="early")
    reply = await thief.orchestrator.handle_message(early)

    assert reply["ok"] is True
    assert len(thief.orchestrator.pending) == 1
    assert "future_message_buffered" in thief.events.names()


async def test_a_buffered_commit_is_not_recorded_early(peer_pair):
    """Held, not applied: ordering is preserved, only rejection is dropped."""
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    await thief.orchestrator.handle_message(commit_envelope(3, mid="early"))

    assert thief.orchestrator.crypto.current.turn == 2
    assert 3 not in thief.orchestrator.crypto.completed_turns


async def test_a_buffered_commit_is_processed_once_the_turn_opens(peer_pair):
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    await thief.orchestrator.handle_message(commit_envelope(3, mid="held"))
    assert len(thief.orchestrator.pending) == 1

    await advance_to(thief, 3)
    await thief.orchestrator._drain_pending(3)

    assert len(thief.orchestrator.pending) == 0
    assert "buffered_message_processed" in thief.events.names()


async def test_two_turns_ahead_is_rejected(peer_pair):
    """One turn of tolerance is a timing allowance, not an open door."""
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    with pytest.raises(FutureTurnMessageError, match="more than"):
        await thief.orchestrator.handle_message(commit_envelope(4, mid="far"))

    assert len(thief.orchestrator.pending) == 0
    assert "future_message_rejected" in thief.events.names()


async def test_max_turns_ahead_is_exactly_one():
    assert MAX_TURNS_AHEAD == 1


async def test_stale_message_is_still_rejected(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    await play_together(cop, thief, 1, Move(Direction.STAY), Move(Direction.STAY))
    await play_together(cop, thief, 2, Move(Direction.STAY), Move(Direction.STAY))

    with pytest.raises((StaleTurnMessageError, Exception)):
        await thief.orchestrator.handle_message(commit_envelope(1, mid="old"))


async def test_exact_retry_of_a_buffered_message_is_idempotent(peer_pair):
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    early = commit_envelope(3, mid="retry-me")
    first = await thief.orchestrator.handle_message(early)
    second = await thief.orchestrator.handle_message(early)

    assert first == second
    assert len(thief.orchestrator.pending) == 1  # not held twice


async def test_conflicting_retry_of_a_buffered_message_is_rejected(peer_pair):
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    await thief.orchestrator.handle_message(
        commit_envelope(3, commitment="a" * 64, mid="same-id")
    )
    with pytest.raises(ConflictingDuplicateError):
        await thief.orchestrator.handle_message(
            commit_envelope(3, commitment="b" * 64, mid="same-id")
        )
    # Caught by the message registry, which sees every message, before it
    # reaches the buffer's own check. Two layers guard the same rule; which one
    # fires first does not matter, only that the conflict is refused.


async def test_a_buffered_reveal_cannot_bypass_commit_ordering(peer_pair):
    """Buffering delays a message; it never lets one overtake another."""
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)

    reveal = new_envelope(
        game_id="test-game", sender_role=Role.POLICE, receiver_role=Role.THIEF,
        message_type=MessageType.REVEAL,
        payload={"sealed": {"v": 1, "turn": 3, "role": "police"}},
        turn_number=3, message_id="early-reveal",
    )
    await thief.orchestrator.handle_message(reveal)

    # Held, and the coordinator has learned nothing about turn 3.
    assert len(thief.orchestrator.pending) == 1
    assert thief.orchestrator.crypto.current.turn == 2

    # Draining it with no prior commit fails, exactly as an on-time reveal with
    # no commit would: buffering delays a message, it never lets one overtake.
    await advance_to(thief, 3)
    with pytest.raises(Exception):
        await thief.orchestrator._drain_pending(3)


async def test_shutdown_clears_the_buffer(peer_pair):
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)
    await thief.orchestrator.handle_message(commit_envelope(3, mid="held"))

    await thief.orchestrator.shutdown("test")

    assert len(thief.orchestrator.pending) == 0
    assert "pending_buffer_cleared" in thief.events.names()


async def test_a_failed_turn_clears_the_buffer(peer_pair):
    cop, thief = peer_pair
    await mid_turn(cop, thief, 2)
    await thief.orchestrator.handle_message(commit_envelope(3, mid="held"))

    # A failed turn raises by design; what matters is the buffer it leaves.
    with pytest.raises(Exception):
        thief.orchestrator._fail_turn(2, "simulated timeout")

    assert len(thief.orchestrator.pending) == 0


async def test_buffer_capacity_comes_from_queue_depth(peer_pair, shared):
    cop, _ = peer_pair
    assert cop.orchestrator.pending.capacity == (
        shared.rate_limiter_gatekeeper.queue_depth
    )


async def test_turns_still_complete_normally_with_the_buffer_in_place(peer_pair):
    """The tolerance must not disturb the ordinary path."""
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    for turn in range(1, 6):
        await play_together(cop, thief, turn, Move(Direction.STAY), Move(Direction.STAY))

    assert len(cop.orchestrator.crypto.completed_turns) == 5
    assert len(cop.orchestrator.pending) == 0
