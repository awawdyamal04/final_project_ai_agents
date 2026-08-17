"""Same GAME COMPLETE banner fix as ``test_gui_banner.py``, against a real Tk
root instead of pure ``banner_for`` calls, plus the information-boundary
guard on the finished view.

Split out further from ``test_gui_banner.py`` (150-line compliance pass,
D-44) purely to stay under the line limit. ``needs_tk``-marked tests skip on
this project's Linux CI/sandbox, which has no display and no ``tkinter``
module at all, and only run for real on a machine with Tk.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from police_thief.gui.view_model import FORBIDDEN_VIEW_FIELDS, LiveView, snapshot


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
def test_banner_shows_game_complete_once_final_status_is_set(peer):
    """Under --hold, a finished match previously left the banner reading
    YOUR TURN because the peer's terminal state fell through _phase_of's
    default of "idle", which _draw_panel treated as actionable. final_status
    is set exactly once, in run.py's shutdown path, and now takes priority
    over phase/peer_state entirely."""
    window = open_window("test", 7)
    try:
        finished = dataclasses.replace(
            snapshot(peer.orchestrator),
            final_status="finished - see terminal for audit result",
        )
        window.render(finished)
        assert window.banner.cget("text") == "GAME COMPLETE"
    finally:
        window.close()


@needs_tk
def test_banner_shows_game_complete_even_after_a_failure(peer):
    """A failed match still reaches the same shutdown path (run.py sets
    final_status either way), so the fix must not depend on success."""
    window = open_window("test", 7)
    try:
        finished = dataclasses.replace(
            snapshot(peer.orchestrator),
            final_status="failed: config_mismatch",
        )
        window.render(finished)
        assert window.banner.cget("text") == "GAME COMPLETE"
    finally:
        window.close()


@needs_tk
def test_banner_unaffected_while_final_status_is_unset(peer):
    """Regression guard: mid-match banner behaviour (YOUR TURN / LOCKED) must
    be exactly what it was before the final_status check was added."""
    window = open_window("test", 7)
    try:
        view = snapshot(peer.orchestrator)
        assert view.final_status is None
        window.render(view)
        assert window.banner.cget("text") in ("YOUR TURN", "LOCKED")
    finally:
        window.close()


def test_finished_view_still_carries_no_forbidden_field(peer, shared):
    """The GAME COMPLETE fix only reads final_status; it must not become a new
    path for opponent information to leak into the finished view."""
    finished = dataclasses.replace(
        snapshot(peer.orchestrator),
        final_status="finished - see terminal for audit result",
    )
    payload = json.dumps(finished.to_dict())
    thief_start = list(shared.board_and_agents.thief_start)

    assert json.dumps(thief_start) not in payload
    for banned in FORBIDDEN_VIEW_FIELDS:
        assert banned not in payload
    assert {f.name for f in dataclasses.fields(finished)} == {
        f.name for f in dataclasses.fields(LiveView)
    }
