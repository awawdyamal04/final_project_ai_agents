"""Drive Tk's own loop on the main thread: rendering, the one-shot screenshot
trigger, and the Ctrl+C/window-close shutdown request.

Split out of ``gui/live.py`` (Q-19, D-44) -- this is the main-thread lifecycle
driver, cohesive on its own and the piece Q-19's screenshot and shutdown
fixes actually live in. ``PeerWindow`` is only needed for its type; imported
under ``TYPE_CHECKING`` so this module carries no runtime dependency on
``gui.live`` (and therefore cannot cycle back to it).
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

from police_thief.gui.capture import ScreenshotOutcome, capture_window, should_capture
from police_thief.gui.view_model import LiveView
from police_thief.gui.view_slot import ViewSlot

if TYPE_CHECKING:
    from police_thief.gui.live import PeerWindow


def drive_on_main_thread(
    window: PeerWindow,
    slot: ViewSlot,
    *,
    interval_ms: int = 120,
    screenshot_path: str | Path | None = None,
) -> ScreenshotOutcome | None:
    """Run Tk's own loop on the main thread, drawing whatever is published.

    Tk must own the main thread. Driving it from a worker crashes the
    interpreter on Windows, and pumping it from the asyncio loop stalls a
    commit exchange past its deadline and fails the turn -- both were tried
    before settling here. The peer's asyncio loop therefore runs in a worker
    and hands frozen snapshots across through ``slot``.

    Two responsibilities beyond drawing:

    * If ``screenshot_path`` is given, the window is captured exactly once,
      on this thread, the first time a *rendered* view carries
      ``final_status`` -- i.e. right after GAME COMPLETE has actually been
      drawn (see ``should_capture``), not after ``mainloop`` returns, by
      which point the window may already be closed or destroyed. The result
      is returned so the caller can report it; ``None`` means no capture was
      ever triggered (no ``screenshot_path``, or the match never reached
      GAME COMPLETE while the window was open).
    * The window closing (the user's X button) or a Ctrl+C landing here both
      ask the worker to unwind via ``slot.request_stop()`` before this
      function returns, instead of leaving the worker sitting in ``--hold``
      until its caller's join timeout abandons it.
    """
    captured: ScreenshotOutcome | None = None

    def _maybe_capture(view: LiveView) -> None:
        nonlocal captured
        if screenshot_path is None or not should_capture(view, captured is not None):
            return
        with contextlib.suppress(Exception):
            captured = capture_window(window, screenshot_path)

    def tick() -> None:
        if window.closed:
            slot.request_stop()
            window.root.quit()
            return
        view = slot.take()
        if view is not None:
            # A rendering fault must never stop the peer.
            with contextlib.suppress(Exception):
                window.render(view)
            _maybe_capture(view)
        if slot.finished:
            window.root.quit()
            return
        window.root.after(interval_ms, tick)

    window.root.after(interval_ms, tick)
    try:
        window.root.mainloop()
    except KeyboardInterrupt:
        # The default SIGINT handler raises this on whichever thread owns
        # the main thread -- here, inside mainloop(). Left uncaught it used
        # to propagate straight out of main(), abandoning the worker thread
        # mid-``--hold`` with no shutdown at all.
        slot.request_stop()
        with contextlib.suppress(Exception):
            window.root.quit()
    except Exception:
        pass

    return captured
