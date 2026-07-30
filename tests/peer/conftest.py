"""Peer test fixtures.

Two wirings are available, and both matter:

* :class:`LoopbackClient` -- calls the opponent's server handler directly, with
  no transport at all. Fast, synchronous to reason about, and used for the bulk
  of the orchestration tests.
* A real :class:`PeerClient` over FastMCP's in-memory transport
  (``Client(fastmcp_instance)``) -- proves the actual client and tool surface
  work, without binding a port.

Real sockets appear only in ``test_two_process.py``, which launches two genuine
OS processes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from police_thief.config.loader import load_private_config, load_shared_config
from police_thief.config.models import PrivateConfig, SharedConfig
from police_thief.peer.client import CallOutcome, PeerClient
from police_thief.peer.clock import FakeClock
from police_thief.peer.deadline import RetryPolicy
from police_thief.peer.events import MemoryEventSink
from police_thief.peer.gatekeeper import Gatekeeper, GatekeeperLimits
from police_thief.peer.orchestrator import PeerOrchestrator
from police_thief.peer.server import PeerServer
from police_thief.protocol.codec import decode_mapping
from police_thief.protocol.exceptions import PeerUnavailableError
from police_thief.protocol.messages import Envelope
from tests.conftest import COP_EXAMPLE_PATH, SHARED_CONFIG_PATH, THIEF_EXAMPLE_PATH


@pytest.fixture
def shared() -> SharedConfig:
    return load_shared_config(SHARED_CONFIG_PATH)


@pytest.fixture
def cop_private() -> PrivateConfig:
    return load_private_config(COP_EXAMPLE_PATH)


@pytest.fixture
def thief_private() -> PrivateConfig:
    return load_private_config(THIEF_EXAMPLE_PATH)


# ----------------------------------------------------------------------
# Loopback client -- no transport
# ----------------------------------------------------------------------


@dataclass
class LoopbackClient:
    """Delivers messages straight into the opponent's server dispatch.

    Implements the same surface as :class:`PeerClient` so an orchestrator
    cannot tell the difference.
    """

    target: PeerServer | None = None
    available: bool = True
    sent: list[Envelope] = field(default_factory=list)
    fail_times: int = 0
    _failures: int = field(default=0, init=False)

    async def health_check(self) -> bool:
        return self.available and self.target is not None

    async def send(self, envelope: Envelope) -> CallOutcome:
        self.sent.append(envelope)
        if not self.available or self.target is None:
            raise PeerUnavailableError("loopback peer is unavailable")
        if self._failures < self.fail_times:
            self._failures += 1
            raise PeerUnavailableError("simulated transient failure")

        data = await self.target.handle_raw(envelope.to_wire())
        if not data.get("ok", False):
            return CallOutcome(
                ok=False,
                error=str(data.get("error")),
                detail=str(data.get("detail", "")),
                retryable=bool(data.get("retryable", False)),
            )
        raw = data.get("envelope")
        return CallOutcome(
            ok=True, envelope=decode_mapping(raw) if raw else None
        )


@dataclass
class PeerHarness:
    """One fully-wired peer, for tests."""

    orchestrator: PeerOrchestrator
    server: PeerServer
    client: LoopbackClient
    events: MemoryEventSink
    clock: FakeClock


def build_peer(
    shared: SharedConfig,
    private: PrivateConfig,
    game_id: str = "test-game",
) -> PeerHarness:
    clock = FakeClock()
    events = MemoryEventSink()
    client = LoopbackClient()
    orchestrator = PeerOrchestrator(
        shared=shared,
        private=private,
        game_id=game_id,
        client=client,  # type: ignore[arg-type]
        events=events,
        clock=clock,
    )
    server = PeerServer(
        peer_name=f"{private.game.group_id}-{private.role.value}",
        handler=orchestrator.handle_message,
        events=events,
        host=private.network.host,
        port=private.network.port,
    )
    return PeerHarness(orchestrator, server, client, events, clock)


@pytest.fixture
def peer_pair(shared, cop_private, thief_private):
    """Two independent peers, each pointed at the other.

    Two separate orchestrators, two separate servers, two separate
    ``LocalState`` objects. Nothing is shared but the protocol.
    """
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server
    return cop, thief


def real_client(
    target_server: PeerServer, shared: SharedConfig, clock=None
) -> PeerClient:
    """A genuine :class:`PeerClient` over FastMCP's in-memory transport."""
    return PeerClient(
        target_server.mcp,
        gatekeeper=Gatekeeper(GatekeeperLimits.from_config(shared), clock),
        retry_policy=RetryPolicy.from_config(shared),
        clock=clock,
    )
