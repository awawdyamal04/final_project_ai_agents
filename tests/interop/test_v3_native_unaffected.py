"""Regression guard for the task's own CRITICAL RULE: mounting reference-v3
onto a peer's FastMCP server must never replace, delete or rewrite the
native protocol -- it is purely additive. This test mounts reference-v3
onto a *real* :class:`PeerServer` (the same object ``peer/run.py`` builds)
and proves the native tools are still there, unchanged, alongside it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client

from police_thief.config.loader import load_shared_config
from police_thief.interop.reference_v3 import mount_reference_v3
from police_thief.peer.server import PeerServer

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


async def _dummy_handler(envelope):
    return {"ok": True, "error": None}


@pytest.mark.asyncio
async def test_native_tools_survive_reference_v3_mounting():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    server = PeerServer(peer_name="test", handler=_dummy_handler)
    state = mount_reference_v3(server.mcp, config=cfg, group_id="group-aaa", role_hint="police")

    async with Client(server.mcp) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}

    # Native tools (peer/server.py's own registration) are unchanged...
    assert {"health_check", "receive_protocol_message"} <= names
    # ...and coexist with the four additive reference-v3 tools.
    assert {"negotiate", "receive_turn", "submit_audit", "receive_control"} <= names
    state.task.cancel()


@pytest.mark.asyncio
async def test_native_health_check_still_answers_normally_when_mounted():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    server = PeerServer(peer_name="test-peer", handler=_dummy_handler)
    state = mount_reference_v3(server.mcp, config=cfg, group_id="group-aaa", role_hint="thief")

    async with Client(server.mcp) as client:
        result = await client.call_tool("health_check", {})
    assert result.data == {"ok": True, "peer": "test-peer"}
    state.task.cancel()


def test_mounting_does_not_require_touching_peer_server_module():
    """Structural check: ``peer/server.py`` -- the native tool registration
    -- has no reference-v3 import at all. The integration point is
    ``peer/run.py`` calling ``mount_reference_v3`` on the already-built
    ``server.mcp``, never a change inside ``PeerServer`` itself."""
    source = (REPO_ROOT / "src" / "police_thief" / "peer" / "server.py").read_text()
    assert "interop" not in source
    assert "reference_v3" not in source
    assert "negotiate" not in source
