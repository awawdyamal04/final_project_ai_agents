"""End-to-end cryptographic turns between two wired peers.

Both peers are driven **concurrently**, which is how the protocol actually runs:
each sends its own commit and waits for the other's. Driving only one side
would let a test pass while the real thing deadlocked.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from police_thief.audit.records import AuditEventType
from police_thief.audit.verifier import verify_chain_file
from police_thief.audit.writer import AuditLog
from police_thief.crypto.exceptions import (
    CommitmentMismatchError,
    ConflictingCommitError,
    CryptoTurnTimeoutError,
)
from police_thief.domain.actions import Move
from police_thief.domain.enums import Direction, Role
from police_thief.peer.states import PeerState
from police_thief.protocol.exceptions import ProtocolValidationError
from police_thief.protocol.messages import MessageType, new_envelope
from tests.peer.conftest import build_peer
from tests.peer.test_orchestrator import drive_to_ready


async def play_together(cop, thief, turn, cop_action, thief_action, **kwargs):
    """Run one turn on both peers at once."""
    return await asyncio.gather(
        cop.orchestrator.play_turn(turn, cop_action, **kwargs),
        thief.orchestrator.play_turn(turn, thief_action, **kwargs),
    )


async def ready_pair(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    return cop, thief


# ----------------------------------------------------------------------
# A complete turn
# ----------------------------------------------------------------------


async def test_two_peers_complete_a_cryptographic_turn(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    cop_saw, thief_saw = await play_together(
        cop, thief, 1, Move(Direction.E), Move(Direction.S)
    )

    assert cop.orchestrator.machine.state is PeerState.TURN_COMPLETE
    assert thief.orchestrator.machine.state is PeerState.TURN_COMPLETE
    # Each learned exactly the other's action -- no more, no less.
    assert cop_saw == Move(Direction.S)
    assert thief_saw == Move(Direction.E)


async def test_commit_precedes_reveal_on_both_sides(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    for peer in (cop, thief):
        kinds = [e.message_type for e in peer.client.sent]
        assert kinds.index(MessageType.COMMIT) < kinds.index(MessageType.REVEAL)


async def test_neither_peer_reveals_before_both_have_committed(peer_pair):
    """The ordering property the whole scheme exists for.

    Reconstructed from the state history: the turn cannot reach REVEAL_ALLOWED
    without first passing BOTH_COMMITS_RECEIVED, and the transition table has
    no other edge into it.
    """
    cop, thief = await ready_pair(peer_pair)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    for peer in (cop, thief):
        states = [t.target for t in peer.orchestrator.machine.history]
        assert states.index(PeerState.BOTH_COMMITS_RECEIVED) < states.index(
            PeerState.REVEAL_ALLOWED
        )
        assert states.index(PeerState.REVEAL_ALLOWED) < states.index(
            PeerState.LOCAL_REVEAL_SENT
        )


async def test_no_action_or_nonce_crosses_the_wire_before_reveal(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    await play_together(
        cop, thief, 1, Move(Direction.E), Move(Direction.S),
        hint="a secret sentence",
    )

    for peer in (cop, thief):
        for envelope in peer.client.sent:
            if envelope.message_type is not MessageType.COMMIT:
                continue
            body = json.dumps(envelope.to_wire())
            assert "a secret sentence" not in body
            assert '"direction"' not in body
            assert "nonce" not in body


async def test_state_progression_is_the_mandatory_order(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    before = len(cop.orchestrator.machine.history)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    assert [t.target for t in cop.orchestrator.machine.history[before:]] == [
        PeerState.SELECTING_ACTION,
        PeerState.LOCAL_ACTION_SEALED,
        PeerState.WAITING_FOR_OPPONENT_COMMIT,
        PeerState.BOTH_COMMITS_RECEIVED,
        PeerState.REVEAL_ALLOWED,
        PeerState.LOCAL_REVEAL_SENT,
        PeerState.WAITING_FOR_OPPONENT_REVEAL,
        PeerState.VERIFYING_REVEAL,
        PeerState.BOTH_REVEALS_VERIFIED,
        PeerState.APPLYING_TURN,
        PeerState.TURN_COMPLETE,
    ]


async def test_several_turns_run_in_sequence(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    for turn in (1, 2, 3):
        await play_together(cop, thief, turn, Move(Direction.E), Move(Direction.S))

    assert len(cop.orchestrator.crypto.completed_turns) == 3
    assert len(cop.orchestrator.crypto.audit_trail) == 3


async def test_nonces_are_unique_across_turns(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    for turn in (1, 2, 3):
        await play_together(cop, thief, turn, Move(Direction.E), Move(Direction.S))

    nonces = [r.nonce for r in cop.orchestrator.crypto.audit_trail]
    assert len(set(nonces)) == 3


# ----------------------------------------------------------------------
# Failure paths
# ----------------------------------------------------------------------


async def test_turn_fails_cleanly_when_the_opponent_never_commits(peer_pair):
    cop, thief = await ready_pair(peer_pair)

    with pytest.raises(CryptoTurnTimeoutError, match="never arrived"):
        await cop.orchestrator.play_turn(1, Move(Direction.E))

    assert cop.orchestrator.machine.state is PeerState.TURN_FAILED
    assert cop.orchestrator.crypto.current is None  # pending nonce discarded
    assert not [
        e for e in cop.client.sent if e.message_type is MessageType.REVEAL
    ]


async def test_abandoned_turn_does_not_expose_the_nonce(peer_pair, capsys):
    cop, thief = await ready_pair(peer_pair)
    with pytest.raises(CryptoTurnTimeoutError):
        await cop.orchestrator.play_turn(1, Move(Direction.E))

    logged = json.dumps(cop.events.records)
    assert "nonce" not in logged
    assert "nonce" not in capsys.readouterr().out


# ----------------------------------------------------------------------
# Protocol-level rejection
# ----------------------------------------------------------------------


async def test_commit_without_a_turn_number_is_rejected(peer_pair):
    cop, _ = await ready_pair(peer_pair)
    wire = new_envelope(
        game_id="test-game",
        sender_role=Role.THIEF,
        receiver_role=Role.POLICE,
        message_type=MessageType.COMMIT,
        payload={"commitment": "a" * 64, "commitment_schema": "1.0"},
        turn_number=1,
    ).to_wire()
    wire["turn_number"] = None

    reply = await cop.server.handle_raw(wire)
    assert reply["ok"] is False
    assert "turn_number" in reply["detail"]


def test_commit_payload_schema_rejects_an_action_field():
    """Leaking a move in the commit is impossible by construction."""
    for leak in ("action", "direction", "nonce", "cell", "hint"):
        with pytest.raises(ProtocolValidationError, match="unknown payload field"):
            new_envelope(
                game_id="g",
                sender_role=Role.POLICE,
                receiver_role=Role.THIEF,
                message_type=MessageType.COMMIT,
                payload={
                    "commitment": "a" * 64,
                    "commitment_schema": "1.0",
                    leak: "x",
                },
                turn_number=1,
            )


def test_reveal_payload_schema_has_no_nonce_field():
    """E-18 enforced at the schema level, not by remembering to omit it."""
    with pytest.raises(ProtocolValidationError, match="unknown payload field"):
        new_envelope(
            game_id="g",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.REVEAL,
            payload={"sealed": {}, "nonce": "a" * 32},
            turn_number=1,
        )


async def test_duplicate_commit_message_is_idempotent(peer_pair):
    cop, _ = await ready_pair(peer_pair)
    envelope = new_envelope(
        game_id="test-game",
        sender_role=Role.THIEF,
        receiver_role=Role.POLICE,
        message_type=MessageType.COMMIT,
        payload={"commitment": "a" * 64, "commitment_schema": "1.0"},
        turn_number=1,
        message_id="fixed",
    )
    first = await cop.orchestrator.handle_message(envelope)
    assert first == await cop.orchestrator.handle_message(envelope)


async def test_conflicting_commit_is_rejected(peer_pair):
    cop, _ = await ready_pair(peer_pair)
    base = dict(
        game_id="test-game",
        sender_role=Role.THIEF,
        receiver_role=Role.POLICE,
        message_type=MessageType.COMMIT,
        turn_number=1,
    )
    await cop.orchestrator.handle_message(
        new_envelope(
            **base,
            payload={"commitment": "a" * 64, "commitment_schema": "1.0"},
            message_id="m1",
        )
    )
    with pytest.raises(ConflictingCommitError):
        await cop.orchestrator.handle_message(
            new_envelope(
                **base,
                payload={"commitment": "b" * 64, "commitment_schema": "1.0"},
                message_id="m2",
            )
        )


# ----------------------------------------------------------------------
# Final reveal and audit
# ----------------------------------------------------------------------


async def test_final_reveal_verifies_a_clean_match(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    for turn in (1, 2):
        await play_together(cop, thief, turn, Move(Direction.E), Move(Direction.S))

    verified = cop.orchestrator.crypto.verify_final_reveal(
        thief.orchestrator.crypto.final_reveal_payload()["records"]
    )
    assert verified == ["turn 1", "turn 2"]

    assert thief.orchestrator.crypto.verify_final_reveal(
        cop.orchestrator.crypto.final_reveal_payload()["records"]
    ) == ["turn 1", "turn 2"]


async def test_final_reveal_travels_over_the_wire_and_verifies(peer_pair):
    cop, thief = await ready_pair(peer_pair)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    verified = await cop.orchestrator.send_final_reveal()
    assert verified == 1


async def test_tampered_action_in_the_final_reveal_is_detected(peer_pair):
    """Caught twice over.

    Changing the action after the turn contradicts what was already revealed,
    so the cross-check fires before the hash comparison is even reached. Both
    detections are correct; this asserts the earlier, more specific one.
    """
    cop, thief = await ready_pair(peer_pair)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    records = thief.orchestrator.crypto.final_reveal_payload()["records"]
    records[0]["action"] = {"v": 1, "kind": "move", "direction": "W"}

    with pytest.raises(CommitmentMismatchError, match="changed after the fact"):
        cop.orchestrator.crypto.verify_final_reveal(records)


async def test_tampered_nonce_is_caught_by_the_hash_comparison(peer_pair):
    """The nonce is the one sealed field absent from the turn reveal, so this
    reaches the SHA-256 recomputation itself -- the path Ch. 5 p. 55 describes.
    """
    cop, thief = await ready_pair(peer_pair)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    records = thief.orchestrator.crypto.final_reveal_payload()["records"]
    records[0]["nonce"] = "c" * 32

    with pytest.raises(CommitmentMismatchError, match="proof of tampering"):
        cop.orchestrator.crypto.verify_final_reveal(records)


# ----------------------------------------------------------------------
# Audit integration
# ----------------------------------------------------------------------


async def test_audit_log_records_the_turn_and_verifies(
    shared, cop_private, thief_private, tmp_path
):
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server
    cop.orchestrator.audit = AuditLog(
        path=tmp_path / "cop.jsonl", game_id="test-game", role="police"
    )

    await drive_to_ready(cop, thief)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    verdict = verify_chain_file(cop.orchestrator.audit.path)
    assert verdict, verdict.describe()

    types = [
        json.loads(line)["event_type"]
        for line in cop.orchestrator.audit.path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert "local_commit" in types
    assert "local_reveal" in types
    assert types.index("local_commit") < types.index("local_reveal")


async def test_audit_log_holds_no_nonce_before_the_final_reveal(
    shared, cop_private, thief_private, tmp_path
):
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server
    cop.orchestrator.audit = AuditLog(
        path=tmp_path / "cop.jsonl", game_id="test-game", role="police"
    )

    await drive_to_ready(cop, thief)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    text = cop.orchestrator.audit.path.read_text(encoding="utf-8")
    assert "nonce" not in text
    for record in cop.orchestrator.crypto.audit_trail:
        assert record.nonce not in text


async def test_commit_record_carries_only_the_commitment(
    shared, cop_private, thief_private, tmp_path
):
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server
    cop.orchestrator.audit = AuditLog(
        path=tmp_path / "cop.jsonl", game_id="test-game", role="police"
    )

    await drive_to_ready(cop, thief)
    await play_together(cop, thief, 1, Move(Direction.E), Move(Direction.S))

    for line in cop.orchestrator.audit.path.read_text(
        encoding="utf-8"
    ).splitlines():
        record = json.loads(line)
        if record["event_type"] == AuditEventType.LOCAL_COMMIT.value:
            assert set(record["payload"]) == {"commitment"}
