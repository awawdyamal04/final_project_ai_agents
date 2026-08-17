"""Q-19, second half: the real end-to-end reproduction, driven over a real
in-process protocol run (LoopbackClient, no sockets, no multi-second sleeps)
rather than mocked -- so this fails against the pre-fix ``run_peer`` shape
and not just against a stub.

Split out of ``test_run_cli.py`` (150-line compliance pass, D-44). The GUI
never left the last ordinary ``turn_complete`` snapshot during ``--hold``,
because ``final_status`` was previously set only in ``run_peer``'s
``finally`` block -- which does not run until Ctrl+C ends the hold.
``banner_for`` itself was already correct; the bug was in *when* the flag it
reads got set.
"""

from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace

from police_thief.peer.gui_runtime import _mark_gui_finished
from police_thief.peer.run import EXIT_OK, _play_turns


class _RecordingSlot:
    """Stands in for gui.view_slot.ViewSlot -- captures every published frame."""

    def __init__(self) -> None:
        self.frames: list = []

    def publish(self, view) -> None:
        self.frames.append(view)


async def test_real_playthrough_reproduces_the_windows_screenshot_then_fixes_it(
    peer_pair,
):
    """The actual reported lifecycle, driven for real:

    ordinary final turn -> _play_turns finishes (turns + final reveal +
    mutual audit all genuinely succeed over the loopback transport) ->
    *before* the fix's publish call, the snapshot a person in --hold would
    have been looking at is exactly the reported bug (YOUR TURN, peer_state
    and phase both turn_complete, final_status unset) -> after the publish
    call run_peer now makes at that point in the control flow, the banner
    is GAME COMPLETE.
    """
    from police_thief.gui.banner import GREEN, GREY, banner_for
    from police_thief.gui.view_model import snapshot
    from police_thief.peer.states import PeerState
    from tests.peer.test_crypto_turn import ready_pair

    cop, thief = await ready_pair(peer_pair)
    args = SimpleNamespace(turns=2, tamper=None, gui=True, gui_delay=0.0)

    cop_code, thief_code = await asyncio.gather(
        _play_turns(cop.orchestrator, args),
        _play_turns(thief.orchestrator, args),
    )
    assert cop_code == EXIT_OK
    assert thief_code == EXIT_OK

    # --- Reproduction: this is the Windows screenshot. ---
    # _play_turns deliberately never touches final_status (it is a run.py/GUI
    # concept, not a protocol one) -- so without the fix's call, this is
    # exactly what a peer sitting in --hold kept publishing.
    for peer in (cop, thief):
        assert peer.orchestrator.machine.state is PeerState.TURN_COMPLETE
        assert peer.orchestrator.final_status is None
        stale_view = snapshot(peer.orchestrator)
        assert stale_view.phase == "turn complete"
        assert banner_for(stale_view) == ("YOUR TURN", GREEN), (
            "reproduction failed: this should be the buggy pre-fix banner"
        )

    # --- Fix: exactly the call run_peer now makes, right after _play_turns
    # returns EXIT_OK, before the --hold wait (see
    # test_gui_slot_is_bound_to_the_stop_event_before_hold for the
    # analogous ordering guarantee, in test_gui_stop_binding.py). ---
    cop_slot, thief_slot = _RecordingSlot(), _RecordingSlot()
    _mark_gui_finished(cop.orchestrator, cop_slot, cop_code)
    _mark_gui_finished(thief.orchestrator, thief_slot, thief_code)

    for slot in (cop_slot, thief_slot):
        final_view = slot.frames[-1]
        assert final_view.final_status is not None
        assert banner_for(final_view) == ("GAME COMPLETE", GREY)


async def test_information_boundary_holds_on_the_final_gui_frame(peer_pair):
    """The completion frame is exactly snapshot(orchestrator) -- same
    function, same boundary as every other frame. Confirms the fix did not
    open a new path for opponent information to leak."""
    from police_thief.gui.view_model import FORBIDDEN_VIEW_FIELDS
    from tests.peer.test_crypto_turn import ready_pair

    cop, thief = await ready_pair(peer_pair)
    args = SimpleNamespace(turns=1, tamper=None, gui=True, gui_delay=0.0)
    await asyncio.gather(
        _play_turns(cop.orchestrator, args),
        _play_turns(thief.orchestrator, args),
    )

    slot = _RecordingSlot()
    _mark_gui_finished(cop.orchestrator, slot, EXIT_OK)
    payload = json.dumps(slot.frames[-1].to_dict())

    for banned in FORBIDDEN_VIEW_FIELDS:
        assert banned not in payload


def test_gui_finished_status_is_set_before_hold_not_only_at_shutdown():
    """Pins the ordering contract statically. Exercising --hold itself needs
    a live process (see the subprocess-based Q-20 tests); this instead
    guards the exact regression: if the call to _mark_gui_finished after
    _play_turns were removed and only the `finally`-block call remained (the
    pre-fix shape -- and the shape that produced the Windows screenshot), a
    peer sitting in --hold would show YOUR TURN for the entire hold
    duration, because `finally` does not run until Ctrl+C ends the wait.
    """
    import inspect

    from police_thief.peer import run as run_module

    source = inspect.getsource(run_module.run_peer)
    calls = [m.start() for m in re.finditer(r"_mark_gui_finished\(", source)]
    assert len(calls) >= 2, (
        "expected at least two call sites: once right after _play_turns "
        "succeeds, once in the shutdown `finally` block"
    )

    hold_index = source.index("await stop.wait()")
    finally_index = source.index("finally:")
    first_call = min(calls)

    assert first_call < hold_index, (
        "_mark_gui_finished must be called before the --hold wait -- "
        "otherwise a finished match is never announced to the GUI until "
        "after the user has already pressed Ctrl+C"
    )
    assert first_call < finally_index, (
        "the pre-hold call site must not itself live inside `finally` -- "
        "that would collapse back to the pre-fix shape"
    )
