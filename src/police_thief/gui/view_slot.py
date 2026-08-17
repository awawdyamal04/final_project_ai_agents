"""``ViewSlot`` -- the one-slot mailbox between the protocol thread and the
Tk main thread, plus the cross-thread shutdown request.

Split out of ``gui/live.py`` (Q-19, D-44): this is a self-contained
concurrency primitive with no Tk dependency at all, so it is worth testing
(and reading) in isolation from rendering.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from police_thief.gui.view_model import LiveView


class ViewSlot:
    """A one-slot mailbox between the protocol thread and the GUI.

    Lock-free by construction: :class:`LiveView` is frozen, so publishing is a
    single reference swap and the reader gets whichever complete view it finds.
    There is no shared mutable structure to tear.

    Also carries the one piece of traffic that goes the *other* way: a
    request from the Tk thread (Ctrl+C, or the window's close button) asking
    the worker to unwind. Before this existed neither trigger reached the
    worker's own ``stop`` event at all -- Ctrl+C raised an uncaught
    ``KeyboardInterrupt`` on the Tk thread, and closing the window just quit
    the Tk loop and left the worker sitting in ``--hold`` until the 60s join
    timeout abandoned it. See ``bind_stop``/``request_stop``.
    """

    def __init__(self) -> None:
        self._latest: LiveView | None = None
        self.finished = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._stop_pending = False

    def publish(self, view: LiveView) -> None:
        self._latest = view

    def take(self) -> LiveView | None:
        return self._latest

    def stop(self, timeout: float = 0.0) -> None:
        self.finished = True

    @property
    def alive(self) -> bool:
        return not self.finished

    # -- cross-thread shutdown request ------------------------------------

    def bind_stop(
        self, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event
    ) -> None:
        """Let another thread ask the worker's own loop to unwind.

        Called once, by the worker itself, right after both objects exist
        (i.e. from inside ``run_peer``, on its own loop). Reading ``_loop``/
        ``_stop_event`` from another thread afterwards is safe under the
        GIL: each is a single reference, assigned exactly once here and never
        reassigned -- the same reasoning ``publish``/``take`` already rely
        on for ``_latest``.
        """
        self._loop = loop
        self._stop_event = stop_event
        if self._stop_pending:
            self.request_stop()

    def request_stop(self) -> None:
        """Ask the worker's own loop to set its shutdown event.

        Safe to call from any thread -- the Tk main thread, a signal handler
        running on it, more than once, or before ``bind_stop`` has happened
        yet (the request is remembered and replayed once binding catches up,
        so a Ctrl+C or window close landing during startup is not silently
        dropped). Uses ``call_soon_threadsafe`` rather than setting the
        ``asyncio.Event`` directly, because ``asyncio.Event`` is not itself
        thread-safe -- it schedules its waiters' wakeups on its own loop, and
        calling ``.set()`` from a different thread races that scheduling.
        """
        loop, stop_event = self._loop, self._stop_event
        if loop is None or stop_event is None:
            self._stop_pending = True
            return
        if loop.is_closed():
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(stop_event.set)
