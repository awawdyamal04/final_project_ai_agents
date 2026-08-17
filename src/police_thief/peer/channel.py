"""One FastMCP session, owned end to end by a single task.

Why a worker task rather than a shared client object
----------------------------------------------------
A FastMCP ``Client`` is an async context manager built on anyio cancel scopes,
and those must be entered and exited **by the same task**. Holding one open
across the peer's lifetime and calling it from whichever coroutine happens to
need it violates that: the session gets entered by the startup task and later
torn down by a turn task, anyio raises ``RuntimeError``, and -- the part that
actually cost the match -- the channel can then never reconnect. Every
subsequent reopen raises ``RuntimeError`` too, so one transient network blip
permanently killed the channel and the opponent simply stopped hearing from us.

So each channel runs a worker task that opens the session, serves requests from
an inbox, and closes it. The session is never touched from outside that task.
Calls are handed over as request objects and awaited through a future, which
also serialises them per channel for free -- and serialisation per channel is
wanted, since a session may only take one call at a time anyway.

A peer keeps two channels against the same opponent so the turn exchange is not
queued behind liveness probes and retries. Two workers, two sessions, two
inboxes, nothing shared.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError

from police_thief.peer.events import EventSink, NullEventSink
from police_thief.protocol.exceptions import (
    InvalidResponseError,
    PeerUnavailableError,
)

MAX_SESSION_RESTARTS = 20
"""Consecutive failed rebuilds before a worker gives up.

Reset to zero whenever a session comes up, so this counts *consecutive*
failures rather than lifetime ones -- otherwise start-up retries against a peer
that has not bound its port yet exhaust the budget before the first turn.

Still bounded: reconnecting forever would turn a dead opponent into an infinite
loop, which is what the deadline tracker exists to prevent.
"""


@dataclass
class _Request:
    tool: str
    arguments: dict[str, Any]
    future: asyncio.Future


@dataclass
class TransportChannel:
    """A named FastMCP session confined to its own worker task."""

    name: str
    transport: Any
    events: EventSink = field(default_factory=NullEventSink)
    max_restarts: int = MAX_SESSION_RESTARTS

    def __post_init__(self) -> None:
        self._inbox: asyncio.Queue[_Request] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._stopping = False
        self.restarts = 0
        self.calls = 0
        self.failures = 0

    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._connected.is_set()

    @property
    def worker(self) -> asyncio.Task[None] | None:
        """Exposed so tests can prove the two channels are independent."""
        return self._task

    async def open(self, timeout: float = 10.0) -> bool:
        """Start the worker and wait briefly for its first connection.

        Returning ``False`` is normal at startup -- the opponent's server may
        simply not be listening yet -- and the worker keeps trying.
        """
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(
                self._run(), name=f"channel-{self.name}"
            )
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
        except TimeoutError:
            return False
        return True

    async def aclose(self) -> None:
        """Stop the worker, letting it close its own session."""
        self._stopping = True
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        self._connected.clear()

    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Own one session for as long as it lasts, then rebuild it."""
        while not self._stopping:
            try:
                async with Client(self.transport) as client:
                    self._connected.set()
                    # A session that came up is proof the opponent is there, so
                    # the restart budget starts again. Without this the budget
                    # is spent on start-up retries before the opponent's server
                    # has even bound its port, and the channel dies at turn 1.
                    self.restarts = 0
                    self.events.emit("channel_open", channel=self.name)
                    await self._serve(client)
            except asyncio.CancelledError:
                self._connected.clear()
                self.events.emit("channel_closed", channel=self.name,
                                 reason="shutdown")
                raise
            except Exception as exc:
                self._connected.clear()
                self.failures += 1
                if self._stopping:
                    return
                if self.restarts >= self.max_restarts:
                    self.events.emit(
                        "channel_exhausted",
                        channel=self.name,
                        restarts=self.restarts,
                        error=type(exc).__name__,
                    )
                    self._drain_with_error(
                        PeerUnavailableError(
                            f"{self.name} channel gave up after "
                            f"{self.restarts} session restarts: "
                            f"{type(exc).__name__}"
                        )
                    )
                    return
                self.restarts += 1
                self.events.emit(
                    "channel_restart",
                    channel=self.name,
                    attempt=self.restarts,
                    error=type(exc).__name__,
                    detail=str(exc)[:160],
                )
                await asyncio.sleep(min(2.0, 0.25 * self.restarts))

    async def _serve(self, client: Client) -> None:
        """Answer requests until the session breaks or we are cancelled."""
        while not self._stopping:
            request = await self._inbox.get()
            if request.future.cancelled():
                continue
            try:
                result = await client.call_tool(
                    request.tool, dict(request.arguments)
                )
            except ToolError as exc:
                # The tool answered and refused; the session is still good.
                if not request.future.done():
                    request.future.set_exception(
                        InvalidResponseError(
                            f"tool {request.tool!r} rejected the call on the "
                            f"{self.name} channel: {exc}"
                        )
                    )
                continue
            except asyncio.CancelledError:
                if not request.future.done():
                    request.future.set_exception(
                        PeerUnavailableError(f"{self.name} channel shutting down")
                    )
                raise
            except Exception as exc:
                # The session itself is suspect. Fail this request and let the
                # outer loop rebuild; the caller's retry policy takes it from
                # here.
                if not request.future.done():
                    request.future.set_exception(
                        PeerUnavailableError(
                            f"{self.name} channel call failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                    )
                raise

            if not request.future.done():
                try:
                    request.future.set_result(
                        _unwrap(result, request.tool, self.name)
                    )
                except Exception as exc:
                    request.future.set_exception(exc)

    def _drain_with_error(self, error: Exception) -> None:
        """Fail everything still queued, rather than leaving callers hanging."""
        while not self._inbox.empty():
            request = self._inbox.get_nowait()
            if not request.future.done():
                request.future.set_exception(error)

    # ------------------------------------------------------------------

    async def call(self, tool: str, arguments: Mapping[str, Any]) -> Any:
        """Ask this channel's worker to invoke a tool."""
        if (
            (self._task is None or self._task.done())
            and not await self.open(timeout=5.0)
            and (self._task is None or self._task.done())
        ):
            raise PeerUnavailableError(f"{self.name} channel is not running")

        loop = asyncio.get_running_loop()
        request = _Request(tool=tool, arguments=dict(arguments), future=loop.create_future())
        self.calls += 1
        await self._inbox.put(request)
        return await request.future


def _unwrap(result: Any, tool: str, channel: str) -> dict[str, Any]:
    if getattr(result, "is_error", False):
        raise InvalidResponseError(
            f"tool {tool!r} returned an error result on the {channel} channel"
        )
    data = getattr(result, "data", None)
    if data is None:
        data = getattr(result, "structured_content", None)
    if not isinstance(data, dict):
        raise InvalidResponseError(
            f"tool {tool!r} returned {type(data).__name__} on the {channel} "
            f"channel, expected an object"
        )
    return data
