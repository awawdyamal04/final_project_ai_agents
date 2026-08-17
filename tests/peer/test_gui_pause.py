"""``_maybe_gui_pause``: the between-turns pacing pause, exercised directly
and in isolation from the rest of ``_play_turns``.

Split out of ``test_run_cli.py`` (150-line compliance pass, D-44). No real
multi-second sleeps: the "pause actually happens" assertions use hundredths
of a second, and everything else is checked without sleeping at all.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from police_thief.peer.gui_runtime import _maybe_gui_pause


class _FakeWatchdog:
    def __init__(self) -> None:
        self.heartbeats = 0

    def heartbeat(self) -> None:
        self.heartbeats += 1


class _FakeOrchestrator:
    """Only exposes ``watchdog`` -- enough for the happy-path pause tests."""

    def __init__(self) -> None:
        self.watchdog = _FakeWatchdog()


class _StrictOrchestrator:
    """Raises if the pause reaches for anything beyond ``watchdog``.

    Proves "delay cannot extend protocol/network waits": there is nothing on
    this object resembling a deadline tracker, retry policy, crypto
    coordinator or client to extend, so any such access fails the test
    immediately rather than silently succeeding against a permissive stub.
    """

    def __init__(self) -> None:
        self.watchdog = _FakeWatchdog()

    def __getattr__(self, name: str):
        raise AssertionError(f"_maybe_gui_pause touched unexpected attribute {name!r}")


async def test_pause_runs_between_turns_and_heartbeats_both_sides():
    orch = _FakeOrchestrator()
    args = SimpleNamespace(gui=True, gui_delay=0.02, turns=3)

    started = time.monotonic()
    await _maybe_gui_pause(args, orch, 1)  # turn 1 of 3: a next turn follows
    elapsed = time.monotonic() - started

    assert elapsed >= 0.015, "the configured pause did not actually elapse"
    assert orch.watchdog.heartbeats == 2, "heartbeat expected before and after"


async def test_pause_does_not_run_after_the_last_turn():
    """No next turn to wait for, so no pause -- matches 'before the next turn
    begins' literally: on the last turn there is no next turn."""
    orch = _FakeOrchestrator()
    args = SimpleNamespace(gui=True, gui_delay=5.0, turns=3)

    started = time.monotonic()
    await _maybe_gui_pause(args, orch, 3)  # turn == args.turns
    elapsed = time.monotonic() - started

    assert elapsed < 0.01
    assert orch.watchdog.heartbeats == 0


async def test_pause_disabled_without_gui():
    orch = _FakeOrchestrator()
    args = SimpleNamespace(gui=False, gui_delay=5.0, turns=3)

    started = time.monotonic()
    await _maybe_gui_pause(args, orch, 1)
    elapsed = time.monotonic() - started

    assert elapsed < 0.01
    assert orch.watchdog.heartbeats == 0


async def test_pause_disabled_when_delay_is_zero():
    orch = _FakeOrchestrator()
    args = SimpleNamespace(gui=True, gui_delay=0.0, turns=3)

    started = time.monotonic()
    await _maybe_gui_pause(args, orch, 1)
    elapsed = time.monotonic() - started

    assert elapsed < 0.01
    assert orch.watchdog.heartbeats == 0


async def test_pause_never_touches_anything_but_the_watchdog():
    """Nothing resembling a deadline, retry, crypto or client object exists on
    this stub, so any access beyond ``.watchdog`` raises -- see
    _StrictOrchestrator."""
    orch = _StrictOrchestrator()
    args = SimpleNamespace(gui=True, gui_delay=0.01, turns=5)

    await _maybe_gui_pause(args, orch, 2)  # must not raise


async def test_pause_never_touches_anything_when_gui_is_off():
    orch = _StrictOrchestrator()
    args = SimpleNamespace(gui=False, gui_delay=5.0, turns=5)

    await _maybe_gui_pause(args, orch, 2)  # must return before touching orch
