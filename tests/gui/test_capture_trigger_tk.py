"""Same screenshot-trigger assertion as ``test_capture_trigger.py``, against
a real Tk root instead of a fake one.

Split out further from ``test_capture_trigger.py`` (150-line compliance
pass, D-44) purely to stay under the line limit -- one behaviour, two
fixture levels.
"""

from __future__ import annotations

import dataclasses

import pytest

from police_thief.gui.capture import ScreenshotOutcome
from police_thief.gui.view_model import snapshot
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
def test_real_window_captures_exactly_once_after_game_complete_renders(
    peer, tmp_path, monkeypatch
):
    """End-to-end against a real Tk root (no real desktop capture --
    capture_window itself is mocked): the capture fires exactly once, and
    only after the banner has actually been drawn as GAME COMPLETE."""
    from police_thief.gui.main_loop import drive_on_main_thread

    calls = []

    def fake_capture(win, path):
        calls.append((win.banner.cget("text"), path))
        return ScreenshotOutcome(str(path), False, "PNG captured")

    monkeypatch.setattr("police_thief.gui.main_loop.capture_window", fake_capture)

    window = open_window("test", 5)
    slot = ViewSlot()
    finished = dataclasses.replace(
        snapshot(peer.orchestrator),
        final_status="finished - see terminal for audit result",
    )
    slot.publish(finished)
    slot.finished = True
    target = tmp_path / "cop.png"

    try:
        outcome = drive_on_main_thread(window, slot, screenshot_path=str(target))
    finally:
        window.close()

    assert len(calls) == 1
    banner_text_at_capture, captured_path = calls[0]
    assert banner_text_at_capture == "GAME COMPLETE", (
        "capture must happen after the frame has actually been rendered"
    )
    assert captured_path == str(target)
    assert outcome.path == str(target)
    assert outcome.ok
