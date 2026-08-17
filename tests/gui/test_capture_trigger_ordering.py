"""The screenshot trigger's re-poll and ordering guarantees: it must not
re-fire on repeated polls of the same finished view, and its outcome must be
populated before the loop reports itself finished.

Split out of ``test_capture_trigger.py`` (150-line compliance pass, D-44)
purely to stay under the line limit -- same fixtures, two more edge cases of
the same trigger.
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


def test_capture_never_refires_on_repeated_polls_of_the_same_finished_view(monkeypatch):
    """The background publisher keeps republishing the same GAME COMPLETE
    view every 0.2s during the 0.6s shutdown grace period; the tick loop
    must not recapture on every one of those re-polls."""
    calls: list = []

    def fake_capture(window, path):
        calls.append(path)
        return ScreenshotOutcome(str(path), False, "PNG captured")

    monkeypatch.setattr("police_thief.gui.main_loop.capture_window", fake_capture)
    window, slot = _FakeWindow(), ViewSlot()
    slot.publish(_view(final_status="finished - see terminal for audit result"))

    seen = {"n": 0}
    real_take = slot.take

    def counting_take():
        seen["n"] += 1
        if seen["n"] >= 5:
            slot.finished = True
        return real_take()

    slot.take = counting_take  # type: ignore[method-assign]

    _drive(window, slot, screenshot_path="evidence/cop.png")

    assert seen["n"] >= 5, "the loop should have polled the same view several times"
    assert len(calls) == 1


def test_capture_happens_before_the_loop_reports_finished(monkeypatch):
    """Ordering: the outcome comes back populated from the same call that
    quits the loop -- capture is not a separate, later step that could be
    skipped by an abandoned thread."""

    def fake_capture(window, path):
        return ScreenshotOutcome(str(path), False, "PNG captured")

    monkeypatch.setattr("police_thief.gui.main_loop.capture_window", fake_capture)
    window, slot = _FakeWindow(), ViewSlot()
    slot.publish(_view(final_status="finished - see terminal for audit result"))
    slot.finished = True

    outcome = _drive(window, slot, screenshot_path="evidence/cop.png")

    assert outcome is not None
    assert outcome.ok
