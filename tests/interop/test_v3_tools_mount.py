"""Reference-v3 adapter -- the four mounted MCP tools themselves.

Every call enqueues and returns ``{"ok": True}`` unconditionally, exactly
like the kit's own reference peer (SPEC: under this wire shape a refusal is
never a tool-call return value). Uses FastMCP's in-memory client transport
(``Client(mcp_instance)``), so no network/port is involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from police_thief.config.loader import load_shared_config
from police_thief.interop.reference_v3 import mount_reference_v3

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


def _mounted():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    mcp = FastMCP(name="test-peer")
    state = mount_reference_v3(mcp, config=cfg, group_id="group-aaa", role_hint="police")
    return mcp, state


@pytest.mark.asyncio
async def test_exactly_the_four_reference_v3_tools_are_registered():
    mcp, state = _mounted()
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"negotiate", "receive_turn", "submit_audit", "receive_control"} <= names
    state.task.cancel()


@pytest.mark.asyncio
async def test_negotiate_acks_immediately_then_the_background_worker_consumes_it():
    """The tool call itself never blocks on processing -- it returns before
    the background ``run()`` task (the queue's real, only consumer) has even
    looked at the message. Proven here by driving that same background
    worker to a real, observable outcome (a refusal, since ``{"terms": {}}``
    is missing every required key) rather than racing it for the queue item
    directly, which two independent consumers of one ``asyncio.Queue`` can
    never both do."""
    mcp, state = _mounted()
    async with Client(mcp) as client:
        result = await client.call_tool("negotiate", {"message": {"terms": {}}})
    assert result.data == {"ok": True}

    import asyncio

    await asyncio.wait_for(state.task, timeout=5.0)
    assert state.result.refusal is not None
    assert "SPAR-N02" in state.result.refusal


@pytest.mark.asyncio
async def test_receive_turn_acks_even_a_structurally_invalid_message():
    """The tool layer never validates synchronously -- that is the whole
    point of the enqueue-and-ack pattern (SPEC section 7.5). Validation
    happens later, on the consuming side (``game_receive.receive_turn``)."""
    mcp, state = _mounted()
    async with Client(mcp) as client:
        result = await client.call_tool("receive_turn", {"message": {"garbage": True}})
    assert result.data == {"ok": True}
    state.task.cancel()


@pytest.mark.asyncio
async def test_submit_audit_and_receive_control_both_ack():
    mcp, state = _mounted()
    async with Client(mcp) as client:
        r1 = await client.call_tool("submit_audit", {"payload": {"sender": "x"}})
        control = {"kind": "status", "sender": "x"}
        r2 = await client.call_tool("receive_control", {"message": control})
    assert r1.data == {"ok": True}
    assert r2.data == {"ok": True}
    state.task.cancel()
