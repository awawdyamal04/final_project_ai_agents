"""The peer's FastMCP server.

Written against **fastmcp 3.4.5** (`mcp` 1.28.1). The API used is exactly:
``FastMCP(name=...)``, the ``@mcp.tool`` decorator, and
``mcp.run_async(transport="http", host=..., port=..., path=...)``.

Every peer runs one of these *and* a client. Ch. 2 (PDF pp. 25-26) is explicit
that this symmetry is the central architectural insight: "each agent is
simultaneously a server exposing tools and a client calling the opponent's
tools. There is no 'strong' side and 'weak' side."

What this layer does **not** do
-------------------------------
It contains no game logic, no strategy, no scoring, no capture evaluation, and
it never touches ``LocalState``. It decodes, validates, and hands a validated
:class:`Envelope` to a single orchestrator callback. That boundary is asserted
statically by ``tests/peer/test_information_boundary.py``, which fails the build
if this module ever imports the domain's scoring, capture or strategy code.

A deliberately small tool surface: one generic validated receiver plus a
liveness probe. The PDF requires no particular tool decomposition -- it shows a
single ``receive_move`` tool as an illustration (PDF p. 28) -- and every extra
tool is another handler that could drift out of step with the others'
validation.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP

from police_thief.peer.events import EventSink, NullEventSink
from police_thief.peer.lifespan_filter import _install_lifespan_cancellation_filter
from police_thief.protocol.codec import decode_mapping
from police_thief.protocol.exceptions import (
    PeerProtocolError,
    ProtocolError,
)
from police_thief.protocol.messages import Envelope, MessageType

MessageHandler = Callable[[Envelope], Awaitable[Mapping[str, Any]]]
"""Signature the orchestrator provides: validated envelope in, wire reply out."""

# The benign-shutdown-cancellation logging filter (Q-19, D-44) now lives in
# police_thief.peer.lifespan_filter, self-contained and independently tested.
# __post_init__ below installs it; see that module for the full reasoning.


@dataclass
class PeerServer:
    """Wraps a :class:`FastMCP` instance and its tool surface."""

    peer_name: str
    handler: MessageHandler
    events: EventSink = NullEventSink()
    host: str = "127.0.0.1"
    port: int = 8801
    path: str = "/mcp"
    # Uvicorn logs one INFO line per request by default; on a shared event loop
    # whose stdout is captured through an undrained pipe, that chatter helps fill
    # the buffer and block the loop (the Q-20 turn-6 freeze). "warning" keeps
    # warnings and errors while removing the per-request flood.
    log_level: str = "warning"

    def __post_init__(self) -> None:
        self.mcp = FastMCP(name=self.peer_name)
        self._register_tools()
        self._task: asyncio.Task[None] | None = None
        _install_lifespan_cancellation_filter()

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        mcp = self.mcp

        @mcp.tool
        async def health_check() -> dict[str, Any]:
            """Liveness probe. Deliberately carries no game information.

            Used by a peer to discover whether its opponent's server is up yet,
            which matters because the two processes start independently and
            either may be first.
            """
            return {"ok": True, "peer": self.peer_name}

        @mcp.tool
        async def receive_protocol_message(
            envelope: dict[str, Any],
        ) -> dict[str, Any]:
            """Accept one protocol message.

            The single ingress point. Decodes and validates, then forwards to
            the orchestrator. Never mutates game state itself.
            """
            return await self._dispatch(envelope)

        # Bound so tests can call them without going through the transport.
        self._health_check = health_check
        self._receive = receive_protocol_message

    async def _dispatch(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and forward, converting every failure into a wire reply.

        Errors are returned as structured ``ok: false`` replies rather than
        raised across the transport, so both peers record the same thing. A
        transport-level exception would leave the sender guessing whether the
        message was rejected or merely lost -- and those need different
        responses (one is retryable, the other is not).
        """
        try:
            envelope = decode_mapping(raw)
        except ProtocolError as exc:
            self.events.emit(
                "inbound_rejected",
                error=type(exc).__name__,
                detail=str(exc)[:200],
            )
            return _error_reply(type(exc).__name__, str(exc), retryable=False)

        self.events.emit(
            "inbound_message",
            message_type=envelope.message_type.value,
            message_id=envelope.message_id,
            sender_role=envelope.sender_role.value,
        )

        try:
            return dict(await self.handler(envelope))
        except PeerProtocolError as exc:
            self.events.emit(
                "inbound_rejected",
                message_id=envelope.message_id,
                error=type(exc).__name__,
                detail=str(exc)[:200],
            )
            return _error_reply(
                type(exc).__name__, str(exc), retryable=exc.retryable
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.events.emit(
                "handler_failed",
                message_id=envelope.message_id,
                error=type(exc).__name__,
            )
            return _error_reply("InternalError", str(exc), retryable=True)

    # ------------------------------------------------------------------
    # Direct access, for tests and in-memory transport
    # ------------------------------------------------------------------

    async def handle_raw(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        """Feed a raw mapping through the same path a tool call takes."""
        return await self._dispatch(raw)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}{self.path}"

    async def serve_forever(self) -> None:
        """Run the HTTP transport until cancelled."""
        await self.mcp.run_async(
            transport="http",
            host=self.host,
            port=self.port,
            path=self.path,
            show_banner=False,
            stateless_http=True,
            json_response=True,
            log_level=self.log_level,
        )

    def start(self) -> asyncio.Task[None]:
        if self._task is None:
            self._task = asyncio.create_task(self.serve_forever())
            self.events.emit("server_ready", url=self.url)
        return self._task

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        # The server task is being torn down; a transport raising on
        # cancellation must not block shutdown. This is *our own* await of
        # the task we just cancelled -- it is not what produces the
        # "Exception in 'lifespan' protocol" ERROR log some shutdowns show;
        # that comes from a separate, uvicorn-internal task this function
        # has no handle to and cannot await directly. See
        # police_thief.peer.lifespan_filter's module docstring.
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


def _error_reply(code: str, detail: str, *, retryable: bool) -> dict[str, Any]:
    return {
        "ok": False,
        "error": code,
        "detail": detail[:500],
        "retryable": retryable,
    }


def ok_reply(envelope: Envelope, message_type: MessageType, **payload: Any) -> dict[str, Any]:
    """Build a successful structured reply carrying a response envelope."""
    return {
        "ok": True,
        "error": None,
        "envelope": envelope.reply(message_type, payload or {}).to_wire(),
    }
