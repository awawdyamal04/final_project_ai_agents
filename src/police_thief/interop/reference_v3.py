"""Mounts the reference-v3 tool surface (SPEC section 7.5) onto an existing
FastMCP server -- **additively**. Every tool here enqueues its payload and
returns ``{"ok": True}`` unconditionally, exactly like the kit's own
reference peer (``sparring/transport/server.py``): under this wire shape a
refusal is never a tool-call return value, so a receiver that tried to
validate synchronously here would simply be speaking a different, stricter
protocol than the one it declared.

**This never touches the native tool surface.** ``mount_reference_v3`` takes
the same ``FastMCP`` instance the native ``PeerServer`` already built
(``server.mcp``) and registers four more tools on it -- coexistence, not
replacement, per the task's own rule. See ``peer/run.py``'s ``--interop
reference-v3`` flag for the one integration point.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.interop.orchestrator import ReferenceV3State, run
from police_thief.peer.events import EventSink, JsonlEventSink, NullEventSink


def mount_reference_v3(
    mcp: Any,
    *,
    config: SharedConfig,
    group_id: str,
    role_hint: str,
    opponent_url: str | None = None,
    timeout: float = 60.0,
    events_path: str | Path | None = None,
    sub_games: int = 1,
) -> ReferenceV3State:
    """Register the four reference-v3 tools on ``mcp`` and start the
    background worker that negotiates and plays one sub-game against
    ``opponent_url`` (if given). Returns the live state object -- read
    ``state.result`` once ``state.task`` completes.

    ``events_path``, if given, records Phase A diagnostics (per-call send
    time, round-trip duration, local/remote terminal decisions) to a JSONL
    file via the same :class:`~police_thief.peer.events.EventSink` the
    native peer already uses for operational telemetry -- distinct from,
    and never written into, the cryptographic audit chain.

    ``sub_games``, if greater than ``1`` (Phase C), plays the full series in
    one run: negotiate, play, audit, repeated per sub-game, alternating
    role exactly as the reference kit does, without restarting this peer or
    reopening the outbound connection. ``state.result.series`` carries the
    per-sub-game rows in that case; the single-game fields on
    ``state.result`` are left at their defaults.
    """
    sink: EventSink = (
        JsonlEventSink(path=Path(events_path), role=role_hint, game_id=group_id)
        if events_path is not None
        else NullEventSink()
    )
    state = ReferenceV3State(
        config=config, group_id=group_id, role_hint=role_hint, opponent_url=opponent_url,
        sink=sink, sub_games=sub_games,
    )

    @mcp.tool
    async def negotiate(message: dict[str, Any]) -> dict[str, Any]:
        """REQUIRED. The pre-game gate: flat terms + nonce + signature +
        identity (SPEC section 4). Either side may open."""
        await state.negotiate_q.put(message)
        return {"ok": True}

    @mcp.tool
    async def receive_turn(message: dict[str, Any]) -> dict[str, Any]:
        """REQUIRED. One TurnMessage per half-turn; the transport is
        symmetric push, so neither peer is purely passive."""
        await state.turn_q.put(message)
        return {"ok": True}

    @mcp.tool
    async def submit_audit(payload: dict[str, Any]) -> dict[str, Any]:
        """REQUIRED. One AuditPayload per sub-game: the sealed chain plus
        nonces, for the opponent to re-hash."""
        await state.audit_q.put(payload)
        return {"ok": True}

    @mcp.tool
    async def receive_control(message: dict[str, Any]) -> dict[str, Any]:
        """OPTIONAL. A status channel touching no game state; answering
        200 is conformant, and that is all this does."""
        await state.control_q.put(message)
        return {"ok": True}

    state.task = asyncio.create_task(run(state, timeout=timeout))
    return state
