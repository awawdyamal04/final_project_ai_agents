"""Real loopback-HTTP regression guard for the Q-20 stateless-transport change.

Unlike the rest of the peer suite (in-memory ``Client(fastmcp_instance)`` or the
``LoopbackClient`` that skips the transport entirely), this test binds a real
localhost port and speaks HTTP to a genuine :class:`PeerServer`. Its single job
is to prove that the patched **stateless** server keeps accepting fresh
connections through many client/session reopen cycles -- the symptom Q-20
reported was a server that stayed alive but stopped accepting new connections.

It deliberately does *not* try to make the old stateful server fail: that
failure was timing-dependent and would be flaky. The guard is one-directional --
the stateless server must survive the churn.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket

import pytest
from fastmcp import Client

from police_thief.domain.enums import Role
from police_thief.peer.server import PeerServer
from police_thief.protocol.messages import MessageType, new_envelope

GAME_ID = "http-stress"
REOPEN_CYCLES = 8
CALLS_PER_CYCLE = 5
CONCURRENT_CALLS = 4
EXPECTED_CALLS = REOPEN_CYCLES * CALLS_PER_CYCLE + CONCURRENT_CALLS + 1


def _free_port() -> int:
    """Grab an available ephemeral localhost port, then release it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


async def _handler(envelope):
    """Trivial echo. The transport is under test here, not any game logic."""
    return {"ok": True, "error": None, "echo": envelope.message_id}


def _wire_message() -> dict:
    return new_envelope(
        game_id=GAME_ID,
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.READY,
    ).to_wire()


async def _await_ready(url: str, timeout: float = 10.0) -> None:
    """Poll a fresh session until the server answers, or fail within ``timeout``."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last: Exception | None = None
    while loop.time() < deadline:
        try:
            async with Client(url) as client:
                result = await asyncio.wait_for(
                    client.call_tool("health_check", {}), timeout=2.0
                )
            if result.data.get("ok"):
                return
        except Exception as exc:  # server not bound yet -- keep polling briefly
            last = exc
            await asyncio.sleep(0.05)
    raise TimeoutError(f"server at {url} never became ready: {last!r}")


async def _one_call(url: str) -> str:
    """One full session: open, call the protocol tool, close. Returns the echo."""
    async with Client(url) as client:
        result = await asyncio.wait_for(
            client.call_tool(
                "receive_protocol_message", {"envelope": _wire_message()}
            ),
            timeout=5.0,
        )
    assert result.data["ok"] is True
    return result.data["echo"]


@contextlib.asynccontextmanager
async def _running_server():
    server = PeerServer(
        peer_name="stress-peer",
        handler=_handler,
        host="127.0.0.1",
        port=_free_port(),
    )
    server.start()
    try:
        await _await_ready(server.url)
        yield server
    finally:
        await server.stop()  # cancels the uvicorn task even if the body raised


@pytest.mark.asyncio
async def test_stateless_server_survives_repeated_real_http_reconnects():
    """45 real HTTP sessions across reopen cycles + a concurrent burst, then a
    final fresh connection that must still be accepted."""
    completed = 0
    async with _running_server() as server:
        url = server.url

        # Consecutive reopen cycles: every call is a brand-new client session.
        for _ in range(REOPEN_CYCLES):
            for _ in range(CALLS_PER_CYCLE):
                assert await _one_call(url)
                completed += 1

        # A small deterministic burst of concurrent independent sessions.
        echoes = await asyncio.wait_for(
            asyncio.gather(*(_one_call(url) for _ in range(CONCURRENT_CALLS))),
            timeout=15.0,
        )
        assert all(echoes)
        completed += len(echoes)

        # The crux: a fresh connection still succeeds after all the churn.
        assert await _one_call(url)
        completed += 1

    assert completed == EXPECTED_CALLS
