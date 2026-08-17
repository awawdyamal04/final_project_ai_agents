"""Two small Q-19 GUI-lifecycle helpers used from ``run_peer``/``_play_turns``.

Split out of ``peer/run.py`` (Q-19, D-44): the final-status publication fix
and the between-turns pacing pause are unrelated to each other except that
both are GUI-only conveniences layered on top of the protocol, never part of
it. Grouped here rather than split further because each is a handful of
lines and neither depends on the other.
"""

from __future__ import annotations

import asyncio


def _mark_gui_finished(orchestrator, gui_slot, exit_code: int) -> None:
    """Set the observer-only completion status and publish one snapshot.

    This is the fix for the second half of Q-19: a *view-state publication*
    problem, not a rendering problem. ``banner_for`` (``gui/banner.py``)
    already checks ``final_status`` first and correctly shows GAME COMPLETE
    once it is set -- the bug was that nothing set it early enough.
    ``final_status`` had only ever been assigned in ``run_peer``'s ``finally``
    block, which does not execute until the whole function is exiting -- i.e.
    after Ctrl+C ends an ``--hold`` wait, not when the protocol work that
    hold is waiting after actually finished. A peer sitting in ``--hold``
    therefore kept publishing fresh snapshots (the background ``run_gui``
    loop polls every 0.2s regardless) whose ``final_status`` was still
    ``None`` and whose ``peer_state``/``phase`` were both frozen at
    ``turn_complete`` -- a value ``banner_for`` treats as "acting" because
    normally it means "between turns, about to start the next one." After the
    last turn that interpretation is simply wrong, which is exactly why the
    fix belongs in *when the flag is set*, not in reinterpreting ``phase``
    for a state it was never meant to describe.

    Idempotent and side-effect-free beyond the orchestrator attribute and the
    one publish, so it is safe to call more than once (e.g. once right after
    ``_play_turns`` succeeds, before ``--hold``, and again at actual shutdown
    to cover the failure paths and the no-``--hold`` path).

    The published view is exactly ``snapshot(orchestrator)`` -- the same
    function and the same information boundary as every other frame; nothing
    about this call adds a new field or a new source of truth.
    """
    from police_thief.gui.view_model import snapshot as _snap
    from police_thief.peer.run import EXIT_OK

    orchestrator.final_status = (
        "finished - see terminal for audit result"
        if exit_code == EXIT_OK
        else f"failed: {orchestrator.failure or 'see terminal'}"
    )
    gui_slot.publish(_snap(orchestrator))


async def _maybe_gui_pause(args, orchestrator, turn: int) -> None:
    """Pace a live GUI between turns. A view-only convenience, not a protocol step.

    Runs only under ``--gui`` with a positive ``--gui-delay``, and only
    strictly *between* turns (never after the last one -- there is no next
    turn to wait for, and the final reveal / mutual audit that follow must
    not be delayed). By the time this is reached, ``play_turn(turn)`` has
    already returned: every commit, reveal, acknowledgement and deadline for
    that turn is settled, and the next turn's deadlines are relative
    (``asyncio.wait_for`` started fresh inside the next ``play_turn`` call),
    not anchored to match start -- so idle time here is invisible to the
    protocol. The watchdog heartbeat on both sides of the sleep is defensive:
    the watchdog loop is not started in the normal run path (see
    ``Watchdog.start``), but if that ever changes, this pause must not read as
    a stall.
    """
    if not args.gui or not args.gui_delay or turn >= args.turns:
        return
    orchestrator.watchdog.heartbeat()
    await asyncio.sleep(args.gui_delay)
    orchestrator.watchdog.heartbeat()
