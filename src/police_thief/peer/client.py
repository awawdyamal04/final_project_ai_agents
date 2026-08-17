"""The peer's FastMCP client.

Written against **fastmcp 3.4.5**: ``Client(transport)`` where transport is
either a URL string (HTTP) or a :class:`FastMCP` instance (in-memory, used by
tests), and ``client.call_tool(name, arguments)`` returning a
``CallToolResult`` whose ``.data`` holds the structured reply. Failures raise
``fastmcp.exceptions.ToolError``.

Every call is bounded three ways: admitted by the Gatekeeper, deadlined by
``response_timeout_sec``, and retried at most ``max_retries`` times with
``retry_backoff_sec`` between attempts. Nothing here retries forever, and
nothing here retries a validation failure -- resending a malformed message
produces the same rejection and spends rate budget for nothing.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from police_thief.peer.channel import TransportChannel
from police_thief.peer.clock import Clock, SystemClock
from police_thief.peer.deadline import DeadlineTracker, RetryPolicy
from police_thief.peer.events import EventSink, NullEventSink
from police_thief.peer.gatekeeper import Gatekeeper
from police_thief.protocol.codec import decode_mapping
from police_thief.protocol.exceptions import (
    InvalidResponseError,
    PeerProtocolError,
    ProtocolError,
)
from police_thief.protocol.messages import Envelope, MessageType


@dataclass(frozen=True, slots=True)
class CallOutcome:
    """The structured result of one protocol call."""

    ok: bool
    envelope: Envelope | None = None
    error: str | None = None
    detail: str | None = None
    retryable: bool = False

    @property
    def rejected(self) -> bool:
        """True when the opponent validly refused the message.

        Distinct from a transport failure: a rejection means the message
        arrived and was understood well enough to be refused, so resending it
        unchanged is pointless.
        """
        return not self.ok and self.error is not None


class PeerClient:
    """Calls the opponent's FastMCP tools."""

    def __init__(
        self,
        transport: Any,
        *,
        gatekeeper: Gatekeeper,
        retry_policy: RetryPolicy,
        clock: Clock | None = None,
        events: EventSink | None = None,
    ) -> None:
        self._transport = transport
        self._gatekeeper = gatekeeper
        self._policy = retry_policy
        self._clock = clock or SystemClock()
        self._events = events or NullEventSink()

        # Two independent sessions against the same opponent server. One
        # session may only be used by one coroutine at a time, so a single
        # shared session means a message in flight blocks everything behind it.
        # Splitting the turn traffic from everything else removes that
        # head-of-line block. Each channel owns its own client and lock and
        # never shares either.
        self._primary = TransportChannel("primary", transport, self._events)
        self._control = TransportChannel("control", transport, self._events)

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    #: Message types that ride the primary channel -- the turn exchange, which
    #: both peers issue simultaneously and which must not be queued behind a
    #: liveness probe or a retry.
    _PRIMARY_TYPES = frozenset(
        {
            MessageType.COMMIT,
            MessageType.REVEAL,
            MessageType.FINAL_REVEAL,
        }
    )

    @property
    def primary(self) -> TransportChannel:
        return self._primary

    @property
    def control(self) -> TransportChannel:
        return self._control

    def channel_for(self, message_type: MessageType) -> TransportChannel:
        """Route deterministically, so both peers agree which path is used."""
        return (
            self._primary
            if message_type in self._PRIMARY_TYPES
            else self._control
        )

    async def open(self) -> None:
        """Establish both sessions at startup."""
        await self._primary.open()
        await self._control.open()

    async def aclose(self) -> None:
        """Close both sessions. Neither failure prevents the other."""
        for channel in (self._primary, self._control):
            with contextlib.suppress(Exception):
                await channel.aclose()

    def diagnostics(self) -> dict[str, Any]:
        """Per-channel counters. Carries no message content."""
        return {
            channel.name: {
                "open": channel.is_open,
                "calls": channel.calls,
                "failures": channel.failures,
                "restarts": channel.restarts,
            }
            for channel in (self._primary, self._control)
        }

    # ------------------------------------------------------------------
    # Raw tool call
    # ------------------------------------------------------------------

    async def _call_tool_once(
        self,
        tool: str,
        arguments: Mapping[str, Any],
        channel: TransportChannel | None = None,
    ) -> Any:
        """One attempt on one channel, with no retry and no admission control.

        Wrapped by :meth:`_guarded`, which adds both.
        """
        return await (channel or self._control).call(tool, arguments)

    async def _guarded(
        self,
        tool: str,
        arguments: Mapping[str, Any],
        *,
        description: str,
        channel: TransportChannel | None = None,
    ) -> Any:
        """One admitted, deadlined, bounded-retry call on ``channel``."""
        tracker = DeadlineTracker(self._policy, self._clock)
        target = channel or self._control

        async def attempt() -> Any:
            async with self._gatekeeper.slot():
                return await self._call_tool_once(tool, arguments, target)

        try:
            return await tracker.run(attempt, description=description)
        finally:
            for record in tracker.attempts:
                if record.error:
                    self._events.emit(
                        "retry",
                        operation=description,
                        channel=target.name,
                        attempt=record.attempt,
                        error=record.error,
                    )

    # ------------------------------------------------------------------
    # Protocol operations
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Is the opponent's server up?

        Returns ``False`` rather than raising when unreachable: during startup
        the opponent legitimately may not exist yet, and the two processes
        start independently with no ordering guarantee.
        """
        try:
            data = await self._call_tool_once(
                "health_check", {}, self._control
            )
        except PeerProtocolError:
            return False
        return bool(data.get("ok"))

    async def send(self, envelope: Envelope) -> CallOutcome:
        """Send a protocol message and interpret the reply.

        The same ``message_id`` is preserved across retries, which is what
        makes a retry idempotent at the far end: the opponent's registry
        recognises the repeat and returns its cached reply instead of acting
        twice.
        """
        channel = self.channel_for(envelope.message_type)
        self._events.emit(
            "outbound_message",
            message_type=envelope.message_type.value,
            message_id=envelope.message_id,
            channel=channel.name,
        )

        data = await self._guarded(
            "receive_protocol_message",
            {"envelope": envelope.to_wire()},
            description=f"{envelope.message_type.value} message",
            channel=channel,
        )
        return self._interpret(data)

    def _interpret(self, data: Mapping[str, Any]) -> CallOutcome:
        if not data.get("ok", False):
            return CallOutcome(
                ok=False,
                error=str(data.get("error", "UnknownError")),
                detail=str(data.get("detail", ""))[:500],
                retryable=bool(data.get("retryable", False)),
            )

        raw = data.get("envelope")
        if raw is None:
            return CallOutcome(ok=True)

        try:
            return CallOutcome(ok=True, envelope=decode_mapping(raw))
        except ProtocolError as exc:
            raise InvalidResponseError(
                f"opponent replied with an invalid envelope: {exc}"
            ) from exc
