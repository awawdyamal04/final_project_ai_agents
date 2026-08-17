"""Ctrl+C / window-close: both ask the worker to stop, and
``drive_on_main_thread`` always returns instead of propagating an uncaught
``KeyboardInterrupt`` or leaving the caller with no way to know shutdown was
requested.

Split out of ``test_drive_main_thread.py`` (150-line compliance pass, D-44).
Tk-free level (fake root/window); ``test_gui_shutdown_tk.py`` covers the same
behaviour against a real Tk root.
"""

from __future__ import annotations

import asyncio

from police_thief.gui.view_slot import ViewSlot


class _FakeRoot:
    """Enough of Tk's root to drive the tick loop without a display."""

    def __init__(self) -> None:
        self._scheduled: list = []
        self._quit_requested = False
        self.quit_calls = 0
        self.raise_on_mainloop: BaseException | None = None

    def after(self, _ms, fn) -> None:
        self._scheduled.append(fn)

    def quit(self) -> None:
        self.quit_calls += 1
        self._quit_requested = True

    def mainloop(self) -> None:
        if self.raise_on_mainloop is not None:
            exc, self.raise_on_mainloop = self.raise_on_mainloop, None
            raise exc
        self._quit_requested = False
        while self._scheduled and not self._quit_requested:
            fn = self._scheduled.pop(0)
            fn()


class _FakeWindow:
    def __init__(self) -> None:
        self.root = _FakeRoot()
        self.closed = False
        self.rendered: list = []

    def render(self, view) -> None:
        self.rendered.append(view)


def _drive(window, slot, **kwargs):
    from police_thief.gui.main_loop import drive_on_main_thread

    return drive_on_main_thread(window, slot, **kwargs)


def test_window_close_requests_worker_stop_before_quitting():
    window, slot = _FakeWindow(), ViewSlot()
    requested: list = []
    slot.request_stop = lambda: requested.append(1)  # type: ignore[method-assign]
    window.closed = True  # simulates the user having already clicked X

    _drive(window, slot)

    assert requested, "closing the window must ask the worker to stop"
    assert window.root.quit_calls == 1


def test_ctrl_c_during_mainloop_requests_stop_and_does_not_propagate():
    window, slot = _FakeWindow(), ViewSlot()
    requested: list = []
    slot.request_stop = lambda: requested.append(1)  # type: ignore[method-assign]
    window.root.raise_on_mainloop = KeyboardInterrupt()

    # Must not raise -- this is exactly the uncaught-KeyboardInterrupt bug
    # that used to abandon the worker thread mid-shutdown.
    _drive(window, slot)

    assert requested, "Ctrl+C must ask the worker to stop, same as closing the window"


def test_request_stop_actually_wakes_a_waiting_stop_event():
    """request_stop (here called from the same thread, for a plain asyncio
    test) really sets the worker's asyncio.Event via call_soon_threadsafe,
    not just a flag nobody reads -- the same mechanism a real cross-thread
    Ctrl+C or window-close relies on."""

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        slot = ViewSlot()
        slot.bind_stop(loop, stop)

        assert not stop.is_set()
        slot.request_stop()
        await asyncio.sleep(0)  # let the scheduled callback run
        assert stop.is_set()

    asyncio.run(scenario())


def test_request_stop_before_bind_stop_is_not_dropped():
    """A stop request landing before the worker has reached bind_stop (e.g.
    during config load or the handshake) must still be honoured once
    binding catches up, not silently lost."""

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        slot = ViewSlot()

        slot.request_stop()  # arrives before bind_stop
        assert not stop.is_set()

        slot.bind_stop(loop, stop)
        await asyncio.sleep(0)
        assert stop.is_set()

    asyncio.run(scenario())


def test_request_stop_is_idempotent_and_safe_to_call_repeatedly():
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        slot = ViewSlot()
        slot.bind_stop(loop, stop)

        slot.request_stop()
        slot.request_stop()
        slot.request_stop()
        await asyncio.sleep(0)

        assert stop.is_set()  # no error, no double-set explosion

    asyncio.run(scenario())


def test_request_stop_before_bind_and_never_bound_is_a_safe_no_op():
    """If the worker never reaches bind_stop at all (e.g. it crashed during
    config load), request_stop must still not raise."""
    slot = ViewSlot()
    slot.request_stop()  # must not raise
    slot.request_stop()
