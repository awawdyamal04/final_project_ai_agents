"""``should_capture`` -- pure, Tk-free trigger logic.

Split out of ``test_capture.py`` (150-line compliance pass, D-44): the trigger
decision and the actual PNG grab are two different responsibilities and were
already organised as two sections in one file; now two files.
"""

from __future__ import annotations

from police_thief.gui.capture import should_capture
from police_thief.gui.view_model import LiveView


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


def test_should_capture_false_before_final_status_is_set():
    """Must not fire on an ordinary in-progress turn."""
    assert should_capture(_view(final_status=None), already_captured=False) is False


def test_should_capture_true_the_first_time_final_status_appears():
    view = _view(final_status="finished - see terminal for audit result")
    assert should_capture(view, already_captured=False) is True


def test_should_capture_false_once_already_captured():
    """One-shot guard: a freshly-published GAME COMPLETE view must not
    retrigger once a capture has already been attempted."""
    view = _view(final_status="finished - see terminal for audit result")
    assert should_capture(view, already_captured=True) is False


def test_should_capture_true_on_a_failure_view_too():
    """A failed match still reaches the same shutdown path and still
    deserves evidence -- the trigger must not depend on success."""
    view = _view(final_status="failed: config_mismatch")
    assert should_capture(view, already_captured=False) is True
    assert should_capture(view, already_captured=True) is False


def test_should_capture_false_when_no_view_has_been_published_yet():
    assert should_capture(None, already_captured=False) is False
