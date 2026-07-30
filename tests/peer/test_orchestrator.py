"""Orchestrator: handshake, identity checks, duplicates, lifecycle."""

from __future__ import annotations

import pytest

from police_thief.config.loader import build_shared_config
from police_thief.domain.enums import Role
from police_thief.peer.orchestrator import PeerOrchestrator
from police_thief.peer.states import PeerState
from police_thief.protocol.exceptions import (
    ConflictingDuplicateError,
    MissingCapabilityError,
    PeerUnavailableError,
    WrongGameIdError,
    WrongReceiverRoleError,
    WrongSenderRoleError,
)
from police_thief.protocol.messages import MessageType, new_envelope
from police_thief.protocol.versions import SOFTWARE_VERSION
from tests.peer.conftest import build_peer


async def drive_to_ready(cop, thief):
    """Run both peers' outbound handshakes, as two independent processes would."""
    cop.orchestrator.mark_server_ready("http://a/mcp")
    thief.orchestrator.mark_server_ready("http://b/mcp")
    assert await cop.orchestrator.wait_for_peer(attempts=1)
    assert await thief.orchestrator.wait_for_peer(attempts=1)
    ok_cop = await cop.orchestrator.perform_handshake()
    ok_thief = await thief.orchestrator.perform_handshake()
    return ok_cop, ok_thief


# ----------------------------------------------------------------------
# Successful lifecycle
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_peers_reach_ready(peer_pair):
    cop, thief = peer_pair
    ok_cop, ok_thief = await drive_to_ready(cop, thief)

    assert ok_cop and ok_thief
    assert cop.orchestrator.machine.state is PeerState.READY
    assert thief.orchestrator.machine.state is PeerState.READY
    assert cop.orchestrator.handshake.complete
    assert thief.orchestrator.handshake.complete


@pytest.mark.asyncio
async def test_both_peers_agree_on_the_config_hash(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)

    assert cop.orchestrator.config_hash == thief.orchestrator.config_hash
    assert (
        cop.orchestrator.handshake.opponent_config_sha256
        == cop.orchestrator.config_hash
    )


@pytest.mark.asyncio
async def test_roles_are_complementary(peer_pair):
    cop, thief = peer_pair
    assert cop.orchestrator.role is Role.POLICE
    assert cop.orchestrator.opponent_role is Role.THIEF
    assert thief.orchestrator.role is Role.THIEF
    assert thief.orchestrator.opponent_role is Role.POLICE


@pytest.mark.asyncio
async def test_state_transition_sequence_is_recorded(peer_pair):
    cop, _ = peer_pair
    await drive_to_ready(*peer_pair)
    assert [t.target for t in cop.orchestrator.machine.history] == [
        PeerState.STARTING,
        PeerState.SERVER_READY,
        PeerState.CONNECTING,
        PeerState.HELLO_EXCHANGE,
        PeerState.CONFIG_EXCHANGE,
        PeerState.CONFIG_VERIFIED,
        PeerState.READY_WAIT,
        PeerState.READY,
    ]


@pytest.mark.asyncio
async def test_handshake_emits_operational_events(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    names = cop.events.names()
    for expected in ("server_ready", "peer_reachable", "handshake_ok", "ready"):
        assert expected in names


@pytest.mark.asyncio
async def test_clean_shutdown(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    await cop.orchestrator.shutdown("test")
    assert cop.orchestrator.machine.state is PeerState.FINISHED
    assert "shutdown" in cop.events.names()


@pytest.mark.asyncio
async def test_shutdown_from_error_is_safe(peer_pair):
    cop, _ = peer_pair
    cop.orchestrator.mark_server_ready("http://a/mcp")
    cop.orchestrator._fail("boom", "test failure")
    await cop.orchestrator.shutdown("after error")
    assert cop.orchestrator.machine.state is PeerState.ERROR


# ----------------------------------------------------------------------
# Failure paths
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_peer_unavailable_leads_to_disconnected(peer_pair):
    cop, _ = peer_pair
    cop.client.available = False
    cop.orchestrator.mark_server_ready("http://a/mcp")

    assert not await cop.orchestrator.wait_for_peer(attempts=3)
    assert cop.orchestrator.machine.state is PeerState.DISCONNECTED
    assert cop.orchestrator.failure == "peer_unavailable"
    assert "peer_unreachable" in cop.events.names()


@pytest.mark.asyncio
async def test_config_mismatch_is_rejected_and_no_turns_begin(
    shared, cop_private, thief_private, valid_shared
):
    """Two peers with different physics must refuse to play (E-11)."""
    valid_shared["world"]["hint_max_words"] = 25  # NEGOTIABLE, so it loads
    other = build_shared_config(valid_shared)

    cop = build_peer(shared, cop_private)
    thief = build_peer(other, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server

    assert cop.orchestrator.config_hash != thief.orchestrator.config_hash

    cop.orchestrator.mark_server_ready("http://a/mcp")
    await cop.orchestrator.wait_for_peer(attempts=1)
    assert not await cop.orchestrator.perform_handshake()

    assert cop.orchestrator.failure == "config_mismatch"
    assert cop.orchestrator.machine.state is PeerState.ERROR
    assert "config_mismatch" in cop.events.names()


@pytest.mark.asyncio
async def test_wrong_game_id_is_rejected(shared, cop_private, thief_private):
    cop = build_peer(shared, cop_private, game_id="game-a")
    thief = build_peer(shared, thief_private, game_id="game-b")
    cop.client.target = thief.server

    envelope = new_envelope(
        game_id="game-a",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.READY,
    )
    with pytest.raises(WrongGameIdError, match="belongs to game"):
        await thief.orchestrator.handle_message(envelope)


@pytest.mark.asyncio
async def test_same_role_opponent_is_rejected(peer_pair):
    """A thief must not accept a message from another thief."""
    _, thief = peer_pair
    envelope = new_envelope(
        game_id="test-game",
        sender_role=Role.THIEF,
        receiver_role=Role.THIEF,
        message_type=MessageType.READY,
    )
    with pytest.raises(WrongSenderRoleError, match="opponent is"):
        await thief.orchestrator.handle_message(envelope)


@pytest.mark.asyncio
async def test_message_addressed_elsewhere_is_rejected(peer_pair):
    cop, _ = peer_pair
    envelope = new_envelope(
        game_id="test-game",
        sender_role=Role.THIEF,
        receiver_role=Role.THIEF,
        message_type=MessageType.READY,
    )
    with pytest.raises((WrongReceiverRoleError, WrongSenderRoleError)):
        await cop.orchestrator.handle_message(envelope)


@pytest.mark.asyncio
async def test_missing_mandatory_capability_is_rejected(peer_pair):
    cop, thief = peer_pair
    envelope = new_envelope(
        game_id="test-game",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.HELLO,
        payload={
            "peer_name": "legacy-peer",
            "software_version": "0.0.1",
            "capabilities": ["handshake.v1"],  # missing canonical-json.v1
        },
    )
    with pytest.raises(MissingCapabilityError, match="canonical-json"):
        await thief.orchestrator.handle_message(envelope)


# ----------------------------------------------------------------------
# Duplicates
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_duplicate_returns_the_same_acknowledgement(peer_pair):
    cop, thief = peer_pair
    envelope = new_envelope(
        game_id="test-game",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.HELLO,
        payload={
            "peer_name": "team-a",
            "software_version": SOFTWARE_VERSION,
            "capabilities": ["handshake.v1", "canonical-json.v1"],
        },
        message_id="fixed",
    )
    first = await thief.orchestrator.handle_message(envelope)
    second = await thief.orchestrator.handle_message(envelope)

    assert first == second
    assert "duplicate_suppressed" in thief.events.names()


@pytest.mark.asyncio
async def test_conflicting_duplicate_is_rejected(peer_pair):
    cop, thief = peer_pair
    base = dict(
        game_id="test-game",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.CONFIG_HASH,
        message_id="reused",
    )
    await thief.orchestrator.handle_message(
        new_envelope(
            **base,
            payload={"config_sha256": "a" * 64, "config_schema_version": "1.2"},
        )
    )
    with pytest.raises(ConflictingDuplicateError, match="different payload"):
        await thief.orchestrator.handle_message(
            new_envelope(
                **base,
                payload={"config_sha256": "b" * 64, "config_schema_version": "1.2"},
            )
        )


@pytest.mark.asyncio
async def test_registry_capacity_comes_from_queue_depth(peer_pair, shared):
    cop, _ = peer_pair
    assert cop.orchestrator.registry.capacity == (
        shared.rate_limiter_gatekeeper.queue_depth
    )


# ----------------------------------------------------------------------
# Status and injection
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_is_safe_to_display(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    status = cop.orchestrator.status()

    assert status["state"] == "ready"
    assert status["role"] == "police"
    assert status["config_sha256"] == cop.orchestrator.config_hash
    # Its own position is legal; the opponent's does not exist.
    assert status["own_position"] == [0, 0]
    for banned in ("opponent_position", "thief_position", "global_state"):
        assert banned not in status


def test_dependencies_are_injected(shared, cop_private):
    """A peer that constructs its own dependencies cannot be tested without a
    network, and an untestable handshake gets debugged during a match."""
    import inspect

    params = set(inspect.signature(PeerOrchestrator).parameters)
    for injected in ("client", "events", "clock", "id_factory", "shared", "private"):
        assert injected in params


@pytest.mark.asyncio
async def test_id_factory_is_injectable(shared, cop_private):
    ids = iter(f"id-{i}" for i in range(100))
    peer = build_peer(shared, cop_private)
    peer.orchestrator.id_factory = lambda: next(ids)
    envelope = peer.orchestrator._envelope(MessageType.READY)
    assert envelope.message_id == "id-0"
