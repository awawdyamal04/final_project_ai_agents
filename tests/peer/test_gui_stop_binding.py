"""Ctrl+C / window-close lifecycle: ``run_peer`` must give the GUI thread a
way to reach ``stop`` before ``--hold``'s indefinite wait begins.

Split out of ``test_run_cli.py`` (150-line compliance pass, D-44). The
mechanism itself (``ViewSlot.bind_stop``/``request_stop``,
``call_soon_threadsafe``) is unit tested directly in
``tests/gui/test_gui_shutdown.py``, which needs no sockets; this pins the
ordering contract inside ``run_peer``, the same way
``test_gui_finished_status_is_set_before_hold_not_only_at_shutdown`` (in
``test_run_gui_playthrough.py``) does for ``_mark_gui_finished``. A full live
``run_peer()`` exercise needs two real bound sockets and a real handshake, so
it belongs to the Windows verification round, not a fast unit test.
"""

from __future__ import annotations

import inspect

from police_thief.peer import run as run_module


def test_gui_slot_is_bound_to_the_stop_event_before_hold():
    """If bind_stop were called after --hold's wait (or not at all), a
    Ctrl+C or window-close landing during --hold would have no way to reach
    the worker's stop event -- exactly the bug this wiring fixes."""
    source = inspect.getsource(run_module.run_peer)
    assert "gui_slot.bind_stop(" in source, "run_peer must bind the stop event to gui_slot"

    bind_index = source.index("gui_slot.bind_stop(")
    hold_index = source.index("await stop.wait()")
    assert bind_index < hold_index, (
        "gui_slot.bind_stop(...) must run before the --hold wait, so a "
        "Ctrl+C/window-close landing at any point up to and including "
        "--hold can reach the worker's own stop event"
    )
