"""``_mark_gui_finished``: the observer-only completion-status publish,
exercised directly.

Split out of ``test_run_cli.py`` (150-line compliance pass, D-44); see
``test_run_gui_playthrough.py`` for the real end-to-end reproduction of the
Q-19 bug this function fixes.
"""

from __future__ import annotations

from police_thief.gui.view_model import snapshot
from police_thief.peer.gui_runtime import _mark_gui_finished
from police_thief.peer.run import EXIT_HANDSHAKE_FAILED, EXIT_OK


class _RecordingSlot:
    """Stands in for gui.view_slot.ViewSlot -- captures every published frame."""

    def __init__(self) -> None:
        self.frames: list = []

    def publish(self, view) -> None:
        self.frames.append(view)


async def test_mark_gui_finished_sets_status_and_publishes_one_frame(peer_pair):
    cop, _thief = peer_pair
    assert cop.orchestrator.final_status is None

    slot = _RecordingSlot()
    _mark_gui_finished(cop.orchestrator, slot, EXIT_OK)

    assert cop.orchestrator.final_status == "finished - see terminal for audit result"
    assert len(slot.frames) == 1
    assert slot.frames[0].final_status == cop.orchestrator.final_status
    assert slot.frames[0] == snapshot(cop.orchestrator)


async def test_mark_gui_finished_reports_the_failure_reason(peer_pair):
    cop, _thief = peer_pair
    cop.orchestrator.failure = "config_mismatch"

    slot = _RecordingSlot()
    _mark_gui_finished(cop.orchestrator, slot, EXIT_HANDSHAKE_FAILED)

    assert cop.orchestrator.final_status == "failed: config_mismatch"
    assert slot.frames[0].final_status == "failed: config_mismatch"


async def test_mark_gui_finished_is_safe_to_call_more_than_once(peer_pair):
    """Called once right after _play_turns succeeds and again in `finally` --
    must not raise, duplicate incorrectly, or change the status."""
    cop, _thief = peer_pair
    slot = _RecordingSlot()

    _mark_gui_finished(cop.orchestrator, slot, EXIT_OK)
    _mark_gui_finished(cop.orchestrator, slot, EXIT_OK)

    assert len(slot.frames) == 2
    assert slot.frames[0].final_status == slot.frames[1].final_status
