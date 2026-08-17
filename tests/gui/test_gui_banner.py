"""The Q-19 fix: ``banner_for`` shows GAME COMPLETE once ``final_status`` is
set, unconditionally of ``phase``/``peer_state``.

Split out of ``test_live_gui.py`` (150-line compliance pass, D-44). Pure and
Tk-free -- runs even where tkinter itself is unavailable. ``test_gui_banner_tk.py``
covers the same fix against a real Tk root.
"""

from __future__ import annotations

import dataclasses

from police_thief.gui.banner import GREEN, GREY, banner_for
from police_thief.gui.view_model import snapshot


def test_banner_for_shows_game_complete_when_final_status_is_set(peer):
    finished = dataclasses.replace(
        snapshot(peer.orchestrator), final_status="finished - see terminal for audit result"
    )
    assert banner_for(finished) == ("GAME COMPLETE", GREY)


def test_banner_for_shows_game_complete_on_failure_too(peer):
    finished = dataclasses.replace(
        snapshot(peer.orchestrator), final_status="failed: config_mismatch"
    )
    assert banner_for(finished) == ("GAME COMPLETE", GREY)


def test_banner_for_ignores_phase_once_final_status_is_set(peer):
    """The whole point of the fix: no phase/peer_state value can override a
    set final_status. Parametrising over the states that previously produced
    the bug (anything _phase_of falls through to "idle" for)."""
    base = snapshot(peer.orchestrator)
    for phase, peer_state in [
        ("idle", "turn_complete"),
        ("choosing action", "ready"),
        ("turn complete", "selecting_action"),
        ("idle", "error"),
    ]:
        finished = dataclasses.replace(
            base, final_status="finished - see terminal for audit result",
            phase=phase, peer_state=peer_state,
        )
        assert banner_for(finished) == ("GAME COMPLETE", GREY), (phase, peer_state)


def test_banner_for_unaffected_while_final_status_is_unset(peer):
    """Regression guard: mid-match banner behaviour (YOUR TURN / LOCKED) is
    exactly what it was before final_status started being checked."""
    view = snapshot(peer.orchestrator)
    assert view.final_status is None
    text, bg = banner_for(view)
    assert text in ("YOUR TURN", "LOCKED")
    assert bg in (GREEN, GREY)
