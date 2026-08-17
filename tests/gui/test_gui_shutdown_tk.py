"""Same shutdown assertion as ``test_gui_shutdown.py``, against a real Tk
root instead of a fake one.

Split out further from ``test_gui_shutdown.py`` (150-line compliance pass,
D-44) purely to stay under the line limit.
"""

from __future__ import annotations

import pytest

from police_thief.gui.view_slot import ViewSlot


def tk_importable() -> bool:
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    return True


needs_tk = pytest.mark.skipif(not tk_importable(), reason="tkinter unavailable")


def open_window(title: str, grid_size: int):
    from police_thief.gui.live import PeerWindow

    try:
        return PeerWindow(title, grid_size)
    except Exception as exc:
        pytest.skip(f"cannot create a Tk root here: {type(exc).__name__}")


@needs_tk
def test_real_window_close_requests_worker_stop():
    """Same assertion as the Tk-free tests in test_gui_shutdown.py, against a
    real Tk root: closing the window must ask the worker to stop instead of
    just quitting the loop and leaving the worker abandoned in --hold."""
    from police_thief.gui.main_loop import drive_on_main_thread

    window = open_window("test", 5)
    slot = ViewSlot()
    requested = []
    slot.request_stop = lambda: requested.append(1)  # type: ignore[method-assign]
    window.closed = True  # simulate the X button having already fired

    try:
        drive_on_main_thread(window, slot)
    finally:
        window.close()

    assert requested
