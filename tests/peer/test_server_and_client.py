"""The FastMCP server tool surface and the real client, over in-memory transport.

Proves the actual fastmcp 3.4.5 API works end to end without binding a port.
Real sockets appear only in ``test_two_process.py``.
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from police_thief.domain.enums import Role
from police_thief.peer.states import PeerState
from police_thief.protocol.messages import MessageType, new_envelope
from police_thief.protocol.versions import SOFTWARE_VERSION
from tests.peer.conftest import build_peer, real_client


@pytest.mark.asyncio
async def test_server_exposes_the_expected_tools(peer_pair):
    cop, _ = peer_pair
    async with Client(cop.server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert names == {"health_check", "receive_protocol_message"}


@pytest.mark.asyncio
async def test_health_check_carries_no_game_information(peer_pair):
    cop, _ = peer_pair
    async with Client(cop.server.mcp) as client:
        result = await client.call_tool("health_check", {})
    assert result.data["ok"] is True
    assert set(result.data) == {"ok", "peer"}


@pytest.mark.asyncio
async def test_real_client_completes_a_handshake_over_in_memory_transport(
    shared, cop_private, thief_private
):
    """The genuine PeerClient against the genuine FastMCP tool surface."""
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)

    cop.orchestrator.client = real_client(thief.server, shared)
    thief.client.target = cop.server

    cop.orchestrator.mark_server_ready("http://a/mcp")
    assert await cop.orchestrator.client.health_check()
    assert await cop.orchestrator.wait_for_peer(attempts=1)
    assert await cop.orchestrator.perform_handshake()
    assert cop.orchestrator.handshake.our_config_accepted


@pytest.mark.asyncio
async def test_malformed_envelope_returns_a_structured_error(peer_pair):
    """Errors come back as ok:false, not as transport exceptions, so both
    peers record the same thing."""
    cop, _ = peer_pair
    reply = await cop.server.handle_raw({"not": "an envelope"})
    assert reply["ok"] is False
    assert reply["error"] == "ProtocolValidationError"
    assert reply["retryable"] is False


@pytest.mark.asyncio
async def test_unknown_message_type_returns_a_structured_error(peer_pair):
    cop, _ = peer_pair
    envelope = new_envelope(
        game_id="test-game",
        sender_role=Role.THIEF,
        receiver_role=Role.POLICE,
        message_type=MessageType.READY,
    ).to_wire()
    envelope["message_type"] = "nonsense"

    reply = await cop.server.handle_raw(envelope)
    assert reply["ok"] is False
    assert reply["error"] == "UnknownMessageTypeError"


@pytest.mark.asyncio
async def test_identity_failure_is_reported_as_non_retryable(peer_pair):
    cop, _ = peer_pair
    envelope = new_envelope(
        game_id="a-different-game",
        sender_role=Role.THIEF,
        receiver_role=Role.POLICE,
        message_type=MessageType.READY,
    )
    reply = await cop.server.handle_raw(envelope.to_wire())
    assert reply["ok"] is False
    assert reply["error"] == "WrongGameIdError"
    assert reply["retryable"] is False


@pytest.mark.asyncio
async def test_server_never_mutates_local_state(peer_pair):
    """The transport layer holds no game authority."""
    cop, thief = peer_pair
    before = thief.orchestrator.state

    for message in (
        new_envelope(
            game_id="test-game",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.HELLO,
            payload={
                "peer_name": "a",
                "software_version": SOFTWARE_VERSION,
                "capabilities": ["handshake.v1", "canonical-json.v1"],
            },
        ),
        new_envelope(
            game_id="test-game",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.CONFIG_HASH,
            payload={
                "config_sha256": thief.orchestrator.config_hash,
                "config_schema_version": "1.2",
            },
        ),
        new_envelope(
            game_id="test-game",
            sender_role=Role.POLICE,
            receiver_role=Role.THIEF,
            message_type=MessageType.READY,
        ),
    ):
        await thief.server.handle_raw(message.to_wire())

    assert thief.orchestrator.state == before
    assert thief.orchestrator.state.position == before.position
    assert thief.orchestrator.state.turn == 0


@pytest.mark.asyncio
async def test_client_reports_peer_unavailable_without_raising(peer_pair):
    cop, _ = peer_pair
    cop.client.available = False
    assert await cop.client.health_check() is False


@pytest.mark.asyncio
async def test_retries_preserve_the_message_id(shared, cop_private, thief_private):
    """Preserving the id is what makes a retry idempotent at the far end."""
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    cop.client.fail_times = 2

    from police_thief.peer.deadline import DeadlineTracker, RetryPolicy

    envelope = cop.orchestrator._envelope(MessageType.READY)
    tracker = DeadlineTracker(RetryPolicy.from_config(shared), cop.clock)
    await tracker.run(lambda: cop.client.send(envelope), description="ready")

    assert len(cop.client.sent) == 3
    assert {e.message_id for e in cop.client.sent} == {envelope.message_id}


@pytest.mark.asyncio
async def test_server_start_and_stop_are_safe_without_a_transport(peer_pair):
    cop, _ = peer_pair
    await cop.server.stop()  # never started; must not raise
