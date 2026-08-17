"""Live GUI: the information boundary, rendering, and the publish loop.

Q-19-specific coverage (banner GAME COMPLETE fix, screenshot trigger,
Ctrl+C/close shutdown) moved out to ``test_gui_banner.py``,
``test_capture_trigger.py`` and ``test_gui_shutdown.py`` (150-line
compliance pass, D-44); this file keeps the pre-existing Phase 7 material.
"""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import json
from pathlib import Path

import pytest

from police_thief.gui.view_model import FORBIDDEN_VIEW_FIELDS, LiveView, snapshot
from police_thief.peer.states import PeerState
from tests.peer.test_orchestrator import drive_to_ready

# ----------------------------------------------------------------------
# The boundary
# ----------------------------------------------------------------------


def test_view_model_field_set_is_exhaustive_and_legal():
    names = {f.name for f in dataclasses.fields(LiveView)}
    assert names == {
        "role", "game_id", "grid_size", "origin_index",
        "own_position", "barriers", "barriers_placed", "barriers_remaining",
        "belief", "scent",
        "peer_state", "connection", "phase", "turn", "turns_completed",
        "opponent_name", "config_sha256", "latest_hint", "latest_hint_intent",
        "error", "final_status",
    }


@pytest.mark.parametrize("banned", sorted(FORBIDDEN_VIEW_FIELDS))
def test_forbidden_fields_are_absent(peer, banned):
    view = snapshot(peer.orchestrator)
    assert banned not in {f.name for f in dataclasses.fields(LiveView)}
    assert not hasattr(view, banned)


def test_snapshot_carries_no_opponent_position(peer, shared):
    """The thief starts at [3,3]; that must appear nowhere in the view."""
    view = snapshot(peer.orchestrator)
    payload = json.dumps(view.to_dict())
    thief_start = list(shared.board_and_agents.thief_start)

    assert view.own_position == tuple(shared.board_and_agents.cop_start)
    assert json.dumps(thief_start) not in payload
    for banned in FORBIDDEN_VIEW_FIELDS:
        assert banned not in payload


def test_view_is_frozen(peer):
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot(peer.orchestrator).turn = 99  # type: ignore[misc]


def test_belief_is_a_distribution_not_a_location(peer):
    """A peak is a guess. It may be wrong, which is why showing it is legal."""
    view = snapshot(peer.orchestrator)
    assert view.belief
    assert 0.0 <= max(view.belief.values()) <= 1.0
    assert sum(view.belief.values()) == pytest.approx(1.0, abs=1e-6)
    assert view.belief_peak in view.belief


def test_gui_never_imports_the_replay_or_the_harness():
    """The replay may show global truth precisely because it is offline."""
    offenders = []
    for path in sorted(Path("src/police_thief/gui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            if isinstance(node, ast.Import):
                names += [a.name for a in node.names]
            for name in names:
                if name.startswith(
                    ("police_thief.replay", "police_thief.sim")
                ):
                    offenders.append(f"{path.name} -> {name}")
    assert not offenders, offenders


def test_snapshot_reads_only(peer):
    """Building a view must not disturb the peer it describes."""
    before = peer.orchestrator.state
    before_turn = peer.orchestrator.state.turn
    before_belief = dict(peer.orchestrator.tracker.belief.probabilities)

    for _ in range(5):
        snapshot(peer.orchestrator)

    assert peer.orchestrator.state == before
    assert peer.orchestrator.state.turn == before_turn
    assert peer.orchestrator.tracker.belief.probabilities == before_belief


def test_snapshot_copies_rather_than_aliases(peer):
    """A later mutation must not reach through an already-rendered frame."""
    view = snapshot(peer.orchestrator)
    cells = len(view.belief)
    peer.orchestrator.tracker.belief.probabilities.clear()
    assert len(view.belief) == cells


async def test_view_reflects_protocol_status(peer_pair):
    cop, thief = peer_pair
    await drive_to_ready(cop, thief)
    view = snapshot(cop.orchestrator)

    assert view.peer_state == PeerState.READY.value
    assert view.connection == "connected"
    assert view.opponent_name is not None
    assert view.config_sha256 == cop.orchestrator.config_hash


def test_view_reports_a_disconnected_peer(peer):
    peer.orchestrator.mark_server_ready("http://x/mcp")
    assert snapshot(peer.orchestrator).connection == "starting"


def test_hint_is_shown_only_once_received(peer):
    """A hint is legal to show: the opponent chose to send it."""
    assert snapshot(peer.orchestrator).latest_hint == ""
    peer.orchestrator.latest_opponent_hint = "slipping past the square"
    peer.orchestrator.latest_opponent_intent = "lie"

    view = snapshot(peer.orchestrator)
    assert view.latest_hint == "slipping past the square"
    assert view.latest_hint_intent == "lie"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def tk_importable() -> bool:
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    return True


needs_tk = pytest.mark.skipif(not tk_importable(), reason="tkinter unavailable")


def open_window(title: str, grid_size: int):
    """Create a window, or skip.

    This Python build (Windows Store) cannot create a *second* Tk root in one
    process -- it fails to locate init.tcl. So a window test that runs after
    another one skips rather than failing, and the real GUI is exercised in its
    own process by the two-process demonstration.
    """
    from police_thief.gui.live import PeerWindow

    try:
        return PeerWindow(title, grid_size)
    except Exception as exc:
        pytest.skip(f"cannot create a Tk root here: {type(exc).__name__}")


@needs_tk
def test_window_renders_and_closes_cleanly(peer):
    view = snapshot(peer.orchestrator)
    window = open_window("test", view.grid_size)
    try:
        window.render(view)
        assert window.pump()
        # One rectangle per cell, at minimum.
        assert len(window.canvas.find_all()) >= view.grid_size**2
    finally:
        window.close()
    assert window.closed
    assert window.pump() is False   # safe after close


@needs_tk
def test_render_draws_belief_scent_and_own_cell(peer):
    from police_thief.domain.coordinates import Coordinate

    peer.orchestrator.tracker.opponent_scent.emit(Coordinate(5, 5))
    view = snapshot(peer.orchestrator)
    assert view.scent, "scent should be visible to the peer that senses it"

    window = open_window("test", view.grid_size)
    try:
        window.render(view)
        items = len(window.canvas.find_all())
        # cells + scent dots + peak marker + own-cell marker and label
        assert items > view.grid_size**2 + 1
    finally:
        window.close()


@needs_tk
def test_banner_locks_once_committed(peer):
    window = open_window("test", 7)
    try:
        window.render(snapshot(peer.orchestrator))
        peer.orchestrator.machine.transition(PeerState.STARTING)
        peer.orchestrator.machine.transition(PeerState.SERVER_READY)
        assert "TURN" in window.banner.cget("text") or "LOCKED" in window.banner.cget(
            "text"
        )
    finally:
        window.close()


# ----------------------------------------------------------------------
# The publish loop
# ----------------------------------------------------------------------


class _StubGui:
    """Stands in for the GUI thread.

    The publish loop has no Tk dependency, and testing it against a stub avoids
    creating Tk on a worker thread inside pytest -- which crashes the
    interpreter, since the main thread has its own Tk state.
    """

    def __init__(self) -> None:
        self.frames: list = []
        self.stopped = False
        self.alive = True

    def publish(self, view) -> None:
        self.frames.append(view)

    def stop(self, timeout: float = 3.0) -> None:
        self.stopped = True
        self.alive = False


async def test_publish_loop_does_not_block_the_protocol(peer):
    """Why Tk gets its own thread: pumping it from the asyncio loop stalled a
    commit exchange past its deadline and failed a turn."""
    import time as _time

    from police_thief.gui.live import run_gui

    gui = _StubGui()
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_gui(gui, lambda: snapshot(peer.orchestrator), stop, interval=0.01)
    )

    started = _time.monotonic()
    await asyncio.sleep(0.05)
    elapsed = _time.monotonic() - started

    assert elapsed < 1.0, f"asyncio loop stalled for {elapsed:.2f}s"
    assert gui.frames, "the GUI should have received frames"
    assert not task.done()

    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert gui.stopped


async def test_published_frames_are_frozen_snapshots(peer):
    """What crosses the thread boundary must be immutable, which is why no
    lock is needed."""
    from police_thief.gui.live import run_gui

    gui = _StubGui()
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_gui(gui, lambda: snapshot(peer.orchestrator), stop, interval=0.01)
    )
    await asyncio.sleep(0.03)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    for frame in gui.frames:
        assert isinstance(frame, LiveView)
        with pytest.raises(dataclasses.FrozenInstanceError):
            frame.turn = 1  # type: ignore[misc]


async def test_snapshot_failure_does_not_kill_the_peer(peer):
    """Losing the window must not forfeit a match."""
    from police_thief.gui.live import run_gui

    gui = _StubGui()
    stop = asyncio.Event()

    def broken():
        raise RuntimeError("snapshot source exploded")

    task = asyncio.create_task(run_gui(gui, broken, stop, interval=0.01))
    await asyncio.sleep(0.05)
    assert not task.done()
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert gui.stopped


# ----------------------------------------------------------------------
# Headless
# ----------------------------------------------------------------------


def test_headless_snapshot_needs_no_display(peer):
    """Everything above the renderer works without a GUI at all."""
    view = snapshot(peer.orchestrator)
    assert view.to_dict()["role"] == "police"


def test_peer_runs_without_the_gui_flag():
    """--gui is opt-in, so existing runs and tests are unchanged."""
    from police_thief.peer.run import _build_parser

    args = _build_parser().parse_args(["--private", "config/cop.toml.example"])
    assert args.gui is False
    assert args.screenshot is None
