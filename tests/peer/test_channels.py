"""Two independent transport channels per peer."""

from __future__ import annotations

import asyncio

import pytest

from police_thief.peer.channel import TransportChannel
from police_thief.peer.client import PeerClient
from police_thief.peer.deadline import RetryPolicy
from police_thief.peer.events import MemoryEventSink
from police_thief.peer.gatekeeper import Gatekeeper, GatekeeperLimits
from police_thief.protocol.exceptions import PeerUnavailableError
from police_thief.protocol.messages import MessageType


def build_client(server, shared, events=None) -> PeerClient:
    return PeerClient(
        server.mcp,
        gatekeeper=Gatekeeper(GatekeeperLimits.from_config(shared)),
        retry_policy=RetryPolicy.from_config(shared),
        events=events or MemoryEventSink(),
    )


# ----------------------------------------------------------------------
# Topology
# ----------------------------------------------------------------------


def test_a_peer_has_two_named_channels(peer_pair, shared):
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    assert client.primary.name == "primary"
    assert client.control.name == "control"


def test_channels_never_share_a_client(peer_pair, shared):
    """The invariant the whole design exists to hold."""
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    assert client.primary is not client.control
    assert client.primary.worker is None and client.control.worker is None


def test_both_channels_point_at_the_same_opponent(peer_pair, shared):
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    assert client.primary.transport is client.control.transport


def test_routing_is_deterministic(peer_pair, shared):
    """Turn traffic on primary; everything else on control, so a commit is
    never queued behind a liveness probe."""
    cop, thief = peer_pair
    client = build_client(thief.server, shared)

    for turn_type in (
        MessageType.COMMIT, MessageType.REVEAL, MessageType.FINAL_REVEAL
    ):
        assert client.channel_for(turn_type) is client.primary

    for other in (
        MessageType.HELLO, MessageType.CONFIG_HASH, MessageType.READY,
        MessageType.ACK, MessageType.ERROR, MessageType.HEALTH_CHECK,
    ):
        assert client.channel_for(other) is client.control

    # Stable across calls.
    assert client.channel_for(MessageType.COMMIT) is client.primary


# ----------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------


async def test_open_starts_both_workers(peer_pair, shared):
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    await client.open()
    try:
        assert client.primary.worker is not None
        assert client.control.worker is not None
        assert client.primary.worker is not client.control.worker
    finally:
        await client.aclose()


async def test_shutdown_closes_both(peer_pair, shared):
    cop, thief = peer_pair
    events = MemoryEventSink()
    client = build_client(thief.server, shared, events)
    await client.open()
    await client.aclose()

    assert not client.primary.is_open
    assert not client.control.is_open
    closed = {r.get("channel") for r in events.events_named("channel_closed")}
    assert closed == {"primary", "control"}


async def test_shutdown_is_idempotent(peer_pair, shared):
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    await client.open()
    await client.aclose()
    await client.aclose()  # must not raise


async def test_diagnostics_report_per_channel_and_carry_no_content(
    peer_pair, shared
):
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    await client.open()
    try:
        await client.health_check()
        diag = client.diagnostics()
    finally:
        await client.aclose()

    assert set(diag) == {"primary", "control"}
    for entry in diag.values():
        assert set(entry) == {"open", "calls", "failures", "restarts"}


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


async def test_simultaneous_calls_on_one_channel_are_serialised(
    peer_pair, shared
):
    """A session may take one call at a time; the worker enforces that."""
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    await client.open()
    try:
        results = await asyncio.gather(
            *(client.health_check() for _ in range(6))
        )
        assert all(results)
    finally:
        await client.aclose()


async def test_a_control_call_proceeds_while_primary_is_busy(peer_pair, shared):
    """The point of two channels: one need not wait for the other."""
    cop, thief = peer_pair
    client = build_client(thief.server, shared)
    await client.open()
    try:
        # Occupy primary, then use control concurrently.
        busy = asyncio.create_task(
            client.primary.call("health_check", {})
        )
        control = await asyncio.wait_for(client.health_check(), timeout=10)
        assert control is True
        await asyncio.wait_for(busy, timeout=10)
    finally:
        await client.aclose()


async def test_one_channel_failing_does_not_disturb_the_other(
    peer_pair, shared
):
    cop, thief = peer_pair
    events = MemoryEventSink()
    client = build_client(thief.server, shared, events)
    await client.open()
    try:
        # Kill primary outright; control must still answer.
        await client.primary.aclose()
        assert not client.primary.is_open
        assert await asyncio.wait_for(client.health_check(), timeout=10)
        assert client.control.is_open
    finally:
        await client.aclose()


async def test_session_restarts_are_bounded():
    """A dead opponent must not become an infinite reconnect loop."""
    channel = TransportChannel(
        "primary", "http://127.0.0.1:1/mcp", MemoryEventSink(), max_restarts=2
    )
    with pytest.raises(PeerUnavailableError):
        await asyncio.wait_for(channel.call("health_check", {}), timeout=30)
    assert channel.restarts <= 2
    await channel.aclose()


async def test_calling_an_unreachable_channel_raises_rather_than_hanging():
    channel = TransportChannel(
        "control", "http://127.0.0.1:1/mcp", MemoryEventSink(), max_restarts=1
    )
    with pytest.raises(PeerUnavailableError):
        await asyncio.wait_for(channel.call("health_check", {}), timeout=30)
    await channel.aclose()
