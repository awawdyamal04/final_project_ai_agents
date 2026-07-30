"""The live peer window (Tkinter).

Draws only a :class:`LiveView`, which by construction cannot carry the
opponent's position. There is no bird's-eye view here and no way to add one
without changing the view model first -- which is the point.

Two display mechanisms, both described in the specification:

* a **belief heatmap** -- deeper colour means higher probability that the hidden
  opponent is in that cell, overlaid with the sensed scent trail;
* a **turn banner** -- green when it is our turn to act, grey once our commit is
  sent and the interface is locked. It is the visual form of the state machine,
  and it is what stops a person acting out of turn.

Threading: Tk owns its own thread. Pumping Tk from the asyncio loop was tried
first and is wrong -- ``update()`` blocks long enough to stall a commit
exchange past its deadline, which fails the turn. Rendering must never be able
to cost a match.

Handing state across the boundary is safe without locks because
:class:`LiveView` is frozen: the protocol thread builds a snapshot and swaps a
single reference, and the GUI thread reads whatever reference it finds. There is
no shared mutable structure to tear.

Headless by omission: if no display is available, or ``--gui`` is not passed,
none of this is constructed and the peer runs exactly as before.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable

from police_thief.gui.view_model import LiveView, snapshot

CELL = 46
PADDING = 14
PANEL_WIDTH = 330

BG = "#12151c"
GRID = "#2b3140"
TEXT = "#e6e9ef"
MUTED = "#8b93a7"
OWN = "#4da3ff"
BARRIER = "#5a6070"
PEAK = "#ffd166"
GREEN = "#2ecc71"
GREY = "#555b6b"
RED = "#ff6b6b"


def _belief_colour(p: float, peak: float) -> str:
    """Deeper red for higher probability, scaled against the current peak."""
    if p <= 1e-9 or peak <= 0:
        return BG
    t = min(1.0, (p / peak) ** 0.6)
    r = int(0x12 + t * (0xE0 - 0x12))
    g = int(0x15 + t * (0x30 - 0x15))
    b = int(0x1C + t * (0x38 - 0x1C))
    return f"#{r:02x}{g:02x}{b:02x}"


class PeerWindow:
    """One peer's live window. Read-only."""

    def __init__(self, title: str, grid_size: int) -> None:
        import tkinter as tk

        self._tk = tk
        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg=BG)
        self.closed = False
        self._last: LiveView | None = None
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        board_px = grid_size * CELL + 2 * PADDING
        self.canvas = tk.Canvas(
            self.root, width=board_px, height=board_px,
            bg=BG, highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, padx=10, pady=10)

        self.panel = tk.Frame(self.root, bg=BG, width=PANEL_WIDTH)
        self.panel.grid(row=0, column=1, sticky="n", padx=(0, 12), pady=10)

        self.banner = tk.Label(
            self.panel, text="", bg=GREY, fg="#11141a",
            font=("Segoe UI", 13, "bold"), width=26, pady=8,
        )
        self.banner.pack(fill="x", pady=(0, 10))

        self.status = tk.Label(
            self.panel, text="", bg=BG, fg=TEXT, justify="left",
            anchor="w", font=("Consolas", 9), width=40,
        )
        self.status.pack(fill="x")

        self.hint = tk.Label(
            self.panel, text="", bg=BG, fg=MUTED, justify="left", anchor="w",
            wraplength=PANEL_WIDTH, font=("Segoe UI", 9, "italic"),
        )
        self.hint.pack(fill="x", pady=(10, 0))

        self.error = tk.Label(
            self.panel, text="", bg=BG, fg=RED, justify="left", anchor="w",
            wraplength=PANEL_WIDTH, font=("Segoe UI", 9),
        )
        self.error.pack(fill="x", pady=(8, 0))

        self.legend = tk.Label(
            self.panel,
            text=(
                "■ you       ▨ barrier\n"
                "red  = belief the opponent is here\n"
                "·    = scent you sense\n"
                "★    = most likely cell (a guess)\n\n"
                "The opponent's true position is not\n"
                "shown, and is not available to show."
            ),
            bg=BG, fg=MUTED, justify="left", anchor="w",
            font=("Segoe UI", 8),
        )
        self.legend.pack(fill="x", pady=(12, 0))

    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self.closed = True

    def render(self, view: LiveView) -> None:
        """Redraw from a snapshot. Never touches the orchestrator.

        Skips the redraw when nothing changed. Between turns most frames are
        identical, and repainting ~100 canvas items regardless holds the GIL
        often enough to starve the peer's worker thread -- which showed up as a
        commit exchange timing out mid-game.
        """
        if self.closed or view == self._last:
            return
        self._last = view
        self._draw_board(view)
        self._draw_panel(view)

    def _draw_board(self, view: LiveView) -> None:
        c = self.canvas
        c.delete("all")
        peak_value = max(view.belief.values(), default=0.0)
        peak_cell = view.belief_peak
        barriers = set(view.barriers)
        origin = view.origin_index

        for row in range(view.grid_size):
            for col in range(view.grid_size):
                cell = (origin + row, origin + col)
                x0 = PADDING + col * CELL
                y0 = PADDING + row * CELL
                x1, y1 = x0 + CELL, y0 + CELL

                if cell in barriers:
                    fill = BARRIER
                else:
                    fill = _belief_colour(view.belief.get(cell, 0.0), peak_value)
                c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=GRID)

                # Scent: a small dot, sized by intensity. It is separate
                # evidence from the belief and worth seeing on its own.
                s = view.scent.get(cell, 0.0)
                if s > 0.02 and cell not in barriers:
                    r = max(2, min(9, int(s * 9)))
                    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                    c.create_oval(
                        cx - r, cy - r, cx + r, cy + r,
                        fill="#7fd1ae", outline="",
                    )

                if peak_cell == cell and cell not in barriers:
                    c.create_text(
                        (x0 + x1) // 2, (y0 + y1) // 2,
                        text="★", fill=PEAK, font=("Segoe UI", 15),
                    )

        row, col = view.own_position
        x0 = PADDING + (col - origin) * CELL
        y0 = PADDING + (row - origin) * CELL
        c.create_rectangle(
            x0 + 6, y0 + 6, x0 + CELL - 6, y0 + CELL - 6,
            fill=OWN, outline="#ffffff", width=2,
        )
        c.create_text(
            x0 + CELL // 2, y0 + CELL // 2,
            text="C" if view.role == "police" else "T",
            fill="#0b1017", font=("Segoe UI", 13, "bold"),
        )

    def _draw_panel(self, view: LiveView) -> None:
        acting = view.phase in ("choosing action", "idle", "turn complete")
        locked = not acting and view.peer_state != "ready"
        self.banner.configure(
            text="LOCKED" if locked else "YOUR TURN",
            bg=GREY if locked else GREEN,
        )

        remaining = (
            f"{view.barriers_remaining}" if view.role == "police" else "n/a"
        )
        self.status.configure(
            text="\n".join(
                [
                    f"role          {view.role}",
                    f"game          {view.game_id}",
                    f"opponent      {view.opponent_name or '—'}",
                    f"connection    {view.connection}",
                    f"peer state    {view.peer_state}",
                    f"phase         {view.phase}",
                    f"turn          {view.turn}"
                    f"  (completed {view.turns_completed})",
                    f"own cell      {view.own_position}",
                    f"barriers      {len(view.barriers)} placed,"
                    f" {remaining} left",
                    f"config        {view.config_sha256[:16]}…",
                ]
            )
        )

        if view.latest_hint:
            self.hint.configure(
                text=f'hint received: "{view.latest_hint}"'
                f"  [declared {view.latest_hint_intent or '?'}]"
            )
        else:
            self.hint.configure(text="hint received: —")

        message = view.final_status or view.error or ""
        self.error.configure(text=message)

    # ------------------------------------------------------------------

    def pump(self) -> bool:
        """Service Tk once. Returns ``False`` when the window has gone."""
        if self.closed:
            return False
        try:
            self.root.update()
        except Exception:
            # The window was destroyed underneath us; treat as a clean close.
            self.closed = True
            return False
        return True

    def close(self) -> None:
        if not self.closed:
            self.closed = True
        try:
            self.root.destroy()
        except Exception:
            pass


class ViewSlot:
    """A one-slot mailbox between the protocol thread and the GUI.

    Lock-free by construction: :class:`LiveView` is frozen, so publishing is a
    single reference swap and the reader gets whichever complete view it finds.
    There is no shared mutable structure to tear.
    """

    def __init__(self) -> None:
        self._latest: LiveView | None = None
        self.finished = False

    def publish(self, view: LiveView) -> None:
        self._latest = view

    def take(self) -> LiveView | None:
        return self._latest

    def stop(self, timeout: float = 0.0) -> None:
        self.finished = True

    @property
    def alive(self) -> bool:
        return not self.finished


async def run_gui(
    gui: "ViewSlot",
    source: Callable[[], LiveView],
    stop: asyncio.Event,
    *,
    interval: float = 0.2,
) -> None:
    """Publish snapshots into the slot until asked to stop.

    Building a snapshot reads orchestrator state, so it must happen on the
    protocol's own loop; only the finished, frozen result crosses the thread
    boundary. If the user closes the window the peer keeps playing -- the GUI
    is an observer, and losing it must not forfeit a match.
    """
    try:
        while not stop.is_set():
            try:
                gui.publish(source())
            except Exception:
                pass  # a failed snapshot must not take the peer down
            await asyncio.sleep(interval)
    finally:
        gui.stop()


def drive_on_main_thread(
    window: PeerWindow, slot: ViewSlot, *, interval_ms: int = 120
) -> None:
    """Run Tk's own loop on the main thread, drawing whatever is published.

    Tk must own the main thread. Driving it from a worker crashes the
    interpreter on Windows, and pumping it from the asyncio loop stalls a
    commit exchange past its deadline and fails the turn -- both were tried
    before settling here. The peer's asyncio loop therefore runs in a worker
    and hands frozen snapshots across through ``slot``.
    """

    def tick() -> None:
        if window.closed:
            window.root.quit()
            return
        view = slot.take()
        if view is not None:
            try:
                window.render(view)
            except Exception:
                pass  # a rendering fault must never stop the peer
        if slot.finished:
            window.root.quit()
            return
        window.root.after(interval_ms, tick)

    window.root.after(interval_ms, tick)
    try:
        window.root.mainloop()
    except Exception:
        pass
