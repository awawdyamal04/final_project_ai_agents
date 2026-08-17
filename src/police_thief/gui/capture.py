"""Automated screenshot evidence for a live window.

Used for the submission evidence, which requires a screenshot of the belief
map and status panel showing a completed match. Two pieces live here:

* :func:`should_capture` -- the pure, Tk-free trigger logic for *when* to
  grab the window. Getting this timing wrong (capturing before GAME COMPLETE
  has actually rendered, or after the window is already gone) is exactly how
  the automated screenshot ended up empty or stale in the first place, so it
  is worth testing in isolation from Tk.
* :func:`capture_window` -- the actual grab. PNG via Pillow's ``ImageGrab``,
  of the full window rectangle (board, banner, status panel, legend), is the
  only format that counts as real evidence. If Pillow is unavailable or the
  grab fails for any reason, we fall back to a PostScript dump of the canvas
  alone -- but that fallback is always reported as degraded (it is missing
  the status panel, and it is not the requested format), never silently
  presented as equivalent. A missing screenshot is a visible gap; a
  fabricated or silently-downgraded one is worse.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from police_thief.gui.view_model import LiveView


@dataclass(frozen=True, slots=True)
class ScreenshotOutcome:
    """What happened when a capture was attempted.

    ``path`` is where a file was actually written, or ``None`` if nothing
    was written at all. ``degraded`` is true only for the EPS fallback. Both
    together let a caller tell "this is the requested PNG evidence" apart
    from "this is a partial substitute" apart from "nothing was captured",
    instead of collapsing all three into one ambiguous ``str | None``.
    ``detail`` is always a human-readable sentence, meant to be printed
    either way, so a missing or degraded screenshot is a visible, explained
    gap rather than a silently accepted one.
    """

    path: str | None
    degraded: bool
    detail: str

    @property
    def ok(self) -> bool:
        """True only for a real PNG, successfully written."""
        return self.path is not None and not self.degraded


def should_capture(view: LiveView | None, already_captured: bool) -> bool:
    """True exactly once per match: the first time a *rendered* view carries
    ``final_status`` -- i.e. right after GAME COMPLETE has actually been
    drawn on screen, not merely published to the cross-thread slot.

    Pure and Tk-free on purpose, for the same reason ``banner_for``
    (``gui/live.py``) is: it is the one piece of capture-trigger logic worth
    testing without a display. Must not fire on an ordinary in-progress turn
    (``final_status is None``) and must not fire twice for the same match
    (``already_captured``), which is what lets the caller poll every 120ms
    without ever recapturing.
    """
    return not already_captured and view is not None and view.final_status is not None


def capture_window(window: Any, path: str | Path) -> ScreenshotOutcome:
    """Capture ``window`` to ``path`` as a PNG.

    Must be called on the same thread that owns ``window`` (Tk is not
    thread-safe). Forces a real repaint via ``update()`` before grabbing --
    the caller may be inside its own Tk callback (e.g. the 120ms polling
    tick), and configuring a widget does not itself guarantee the pixels have
    reached the screen yet.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        window.root.update()
    except Exception as exc:
        return ScreenshotOutcome(
            None, False, f"window unavailable: {type(exc).__name__}: {exc}"
        )

    try:
        from PIL import ImageGrab  # type: ignore
    except ImportError as exc:
        return _eps_fallback(window, target, f"Pillow not installed ({exc})")

    try:
        root = window.root
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        image = ImageGrab.grab(
            bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())
        )
        image.save(target)
        return ScreenshotOutcome(str(target), False, f"PNG captured via ImageGrab -> {target}")
    except Exception as exc:
        return _eps_fallback(
            window, target, f"ImageGrab failed: {type(exc).__name__}: {exc}"
        )


def _eps_fallback(window: Any, target: Path, reason: str) -> ScreenshotOutcome:
    """Last resort: a PostScript dump of the canvas only (no status panel).

    Always reported as degraded via ``ScreenshotOutcome.degraded`` -- never
    silently equivalent to the requested PNG.
    """
    try:
        eps = target.with_suffix(".eps")
        window.canvas.postscript(file=str(eps), colormode="color")
        return ScreenshotOutcome(
            str(eps),
            True,
            f"{reason}; wrote a degraded EPS fallback (canvas only, no status "
            "panel) instead of the requested PNG",
        )
    except Exception as exc:
        return ScreenshotOutcome(
            None,
            False,
            f"{reason}; EPS fallback also failed: {type(exc).__name__}: {exc}",
        )
