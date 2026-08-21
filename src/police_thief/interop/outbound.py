"""A persistent, reconnect-tolerant outbound reference-v3 MCP session
(Phase B).

One FastMCP ``Client`` connection is opened once and reused across
negotiation, every turn in a sub-game, and its audit exchange --
replacing the original design, which opened and closed a fresh
``Client(url)`` **per call**. That per-call construction cost several
extra HTTP round trips each time (observed live against the real kit:
POST/POST/GET/POST/POST/DELETE for a single tool call) -- exactly the
kind of avoidable latency that can push a message past the opponent's own
per-message deadline (``budgets.turn_timeout``, ``sparring/deadlines.py``).
See Phase A's ``outbound_call_start``/``outbound_call_end`` events for how
that latency is now measured, before and after this change.

Split out of ``orchestrator.py`` to keep that file under the project's
150-line limit; this is a single, self-contained concern.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError

from police_thief.peer.events import EventSink, NullEventSink

_NULL_SINK = NullEventSink()


class OutboundSession:
    """One reusable connection to ``url``. Connects lazily on the first
    call; reconnects automatically, once, if the connection drops
    mid-series. Resending after a reconnect is safe by the wire's own
    delivery contract: every reference-v3 tool call carries a sealed
    ``commit``, and a redelivered ``step``/``commit`` pair is *absorbed* as
    a duplicate, never treated as an equivocation (:mod:`delivery`) --
    only a genuinely *different* commit at an already-played step is.
    """

    def __init__(self, url: str, *, sink: EventSink | None = None) -> None:
        self.url = url
        self.sink = sink or _NULL_SINK
        self._client: Client | None = None

    async def _ensure_connected(self, retry_for: float) -> Client:
        if self._client is not None and self._client.is_connected():
            return self._client
        deadline = asyncio.get_event_loop().time() + retry_for
        while True:
            try:
                client = Client(self.url)
                await client.__aenter__()
                self._client = client
                self.sink.emit("outbound_session_connected", url=self.url)
                return client
            except Exception:
                if asyncio.get_event_loop().time() >= deadline:
                    raise
                await asyncio.sleep(1.0)

    async def call(
        self,
        tool: str,
        arg_name: str,
        payload: dict[str, Any],
        *,
        retry_for: float = 20.0,
        deadline_at: float | None = None,
    ) -> dict[str, Any]:
        """Call one reference-v3 tool over the shared connection, tolerating
        both the initial startup race and a mid-series drop. Never retries
        a :class:`ToolError` -- the message arrived and was understood, so
        resending it is not the fix."""
        started = time.monotonic()
        remaining = None if deadline_at is None else round(deadline_at - started, 3)
        self.sink.emit("outbound_call_start", tool=tool, remaining_before_s=remaining)

        client = await self._ensure_connected(retry_for)
        for attempt in (1, 2):
            try:
                res = await client.call_tool(tool, {arg_name: payload})
                data = res.data if isinstance(res.data, dict) else {}
                self._emit_end(tool, started, attempt, ok=True)
                return data
            except ToolError:
                self._emit_end(tool, started, attempt, ok=False, reason="tool_error")
                raise
            except Exception:  # connection dropped mid-call
                if attempt == 2:
                    self._emit_end(tool, started, attempt, ok=False, reason="reconnect_failed")
                    raise
                self._client = None
                client = await self._ensure_connected(retry_for)
        raise AssertionError("unreachable")  # pragma: no cover

    def _emit_end(
        self, tool: str, started: float, attempt: int, *, ok: bool, reason: str = ""
    ) -> None:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        fields: dict[str, Any] = {
            "tool": tool, "attempt": attempt, "elapsed_ms": elapsed_ms, "ok": ok,
        }
        if reason:
            fields["reason"] = reason
        self.sink.emit("outbound_call_end", **fields)

    async def close(self) -> None:
        """Close cleanly at shutdown -- idempotent, safe to call even if
        never connected or already dropped."""
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            finally:
                self._client = None
                self.sink.emit("outbound_session_closed", url=self.url)
