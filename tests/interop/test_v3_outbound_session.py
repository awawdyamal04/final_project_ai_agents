"""``OutboundSession`` (Phase B): one persistent connection reused across
calls, replacing the original per-call ``Client(url)`` construction.

Uses FastMCP's in-memory transport (``Client(mcp_instance)``, no network),
which is enough to prove connection reuse, event emission, close semantics,
and that a tool-level refusal is never retried. A genuine mid-series
network drop and reconnect cannot be reproduced over an in-memory
transport -- that remains a live/network-only concern, exercised in the
real external sparring run (Phase F), not here.
"""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from police_thief.interop.outbound import OutboundSession
from police_thief.peer.events import MemoryEventSink


def _server() -> FastMCP:
    mcp = FastMCP(name="fake-opponent")
    calls: list[str] = []

    @mcp.tool
    async def negotiate(message: dict) -> dict:
        calls.append("negotiate")
        return {"ok": True}

    @mcp.tool
    async def receive_turn(message: dict) -> dict:
        calls.append("receive_turn")
        return {"ok": True}

    @mcp.tool
    async def boom(message: dict) -> dict:
        raise ToolError("refused")

    mcp._test_calls = calls  # type: ignore[attr-defined]
    return mcp


@pytest.mark.asyncio
async def test_one_connection_is_reused_across_several_calls():
    mcp = _server()
    session = OutboundSession(mcp)
    await session.call("negotiate", "message", {"a": 1})
    first_client = session._client
    await session.call("receive_turn", "message", {"b": 2})
    await session.call("receive_turn", "message", {"c": 3})
    assert session._client is first_client  # same connection, not reopened
    assert mcp._test_calls == ["negotiate", "receive_turn", "receive_turn"]  # type: ignore[attr-defined]
    await session.close()


@pytest.mark.asyncio
async def test_close_is_idempotent_and_safe_before_any_call():
    session = OutboundSession(_server())
    await session.close()  # never connected
    await session.call("negotiate", "message", {})
    await session.close()
    await session.close()  # already closed
    assert session._client is None


@pytest.mark.asyncio
async def test_a_tool_refusal_is_never_retried():
    """A :class:`ToolError` means the message arrived and was understood --
    resending it would not change the answer, so it must propagate on the
    first attempt, not trigger the reconnect-and-resend path."""
    session = OutboundSession(_server())
    with pytest.raises(ToolError):
        await session.call("boom", "message", {})
    await session.close()


@pytest.mark.asyncio
async def test_call_emits_start_and_end_events_with_timing():
    sink = MemoryEventSink()
    session = OutboundSession(_server(), sink=sink)
    await session.call("negotiate", "message", {})
    names = sink.names()
    assert names.count("outbound_call_start") == 1
    assert names.count("outbound_call_end") == 1
    end = sink.events_named("outbound_call_end")[0]
    assert end["ok"] is True
    assert end["tool"] == "negotiate"
    assert isinstance(end["elapsed_ms"], float)
    await session.close()


@pytest.mark.asyncio
async def test_connect_and_close_events_are_emitted_once_each():
    sink = MemoryEventSink()
    session = OutboundSession(_server(), sink=sink)
    await session.call("negotiate", "message", {})
    await session.call("negotiate", "message", {})
    assert sink.names().count("outbound_session_connected") == 1
    await session.close()
    assert sink.names().count("outbound_session_closed") == 1
