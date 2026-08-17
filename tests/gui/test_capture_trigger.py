"""The screenshot trigger wired into ``drive_on_main_thread``'s tick loop:
exactly once, only after GAME COMPLETE, only with ``--screenshot``, never
re-fired by the 120ms poll.

Split out of ``test_drive_main_thread.py`` (150-line compliance pass, D-44).
Tk-free level (fake root/window), covering the CI/sandbox path, which has no
display and no ``tkinter`` module at all. ``test_capture_trigger_tk.py``
covers the same behaviour against a real Tk root; the re-poll and ordering
edge cases of this same trigger live in ``test_capture_trigger_ordering.py``.
"""

from __future__ import annotations

from police_thief.gui.capture import ScreenshotOutcome
from police_thief.gui.view_model import LiveView
from police_thief.gui.view_slot import ViewSlot


def _view(final_status: str | None = None) -> LiveView:
    return LiveView(
        role="police",
        game_id="g",
        grid_size=5,
        origin_index=0,
        own_position=(0, 0),
        barriers=(),
        barriers_placed=0,
        barriers_remaining=3,
        final_status=final_status,
    )


class _FakeRoot:
    """Enough of Tk's root to drive the tick loop without a display."""

    def __init__(self) -> None:
        self._scheduled: list = []
        self._quit_requested = False
        self.quit_calls = 0

    def after(self, _ms, fn) -> None:
        self._scheduled.append(fn)

    def quit(self) -> None:
        self.quit_calls += 1
        self._quit_requested = True

    def mainloop(self) -> None:
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


def test_no_capture_without_a_screenshot_path(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        "police_thief.gui.main_loop.capture_window",
        lambda *a, **k: calls.append(1) or ScreenshotOutcome("x", False, "ok"),
    )
    window, slot = _FakeWindow(), ViewSlot()
    slot.publish(_view(final_status="finished - see terminal for audit result"))
    slot.finished = True

    outcome = _drive(window, slot, screenshot_path=None)

    assert outcome is None
    assert not calls


def test_no_capture_on_an_ordinary_in_progress_turn(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        "police_thief.gui.main_loop.capture_window",
        lambda *a, **k: calls.append(1) or ScreenshotOutcome("x", False, "ok"),
    )
    window, slot = _FakeWindow(), ViewSlot()
    slot.publish(_view(final_status=None))  # ordinary turn, no completion yet
    slot.finished = True

    outcome = _drive(window, slot, screenshot_path="evidence/cop.png")

    assert outcome is None
    assert not calls


def test_capture_fires_exactly_once_when_game_completes(monkeypatch):
    calls: list = []

    def fake_capture(window, path):
        calls.append(path)
        return ScreenshotOutcome(str(path), False, "PNG captured")

    monkeypatch.setattr("police_thief.gui.main_loop.capture_window", fake_capture)
    window, slot = _FakeWindow(), ViewSlot()
    slot.publish(_view(final_status="finished - see terminal for audit result"))
    slot.finished = True

    outcome = _drive(window, slot, screenshot_path="evidence/cop.png")

    assert calls == ["evidence/cop.png"]
    assert outcome.path == "evidence/cop.png"
    assert outcome.ok
