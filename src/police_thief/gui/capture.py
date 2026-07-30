"""Save a screenshot of a live window.

Used for the submission evidence, which requires a screenshot of the belief map
(and one of the replay viewer showing its verification stamp).

Tk cannot write a PNG of an arbitrary window on its own. The most reliable
route without adding a dependency is a PostScript dump of the canvas, which Tk
does support, converted if a converter happens to be available. Failing that we
fall back to grabbing the window rectangle from the screen, and if neither
works we return ``None`` rather than pretending -- a missing screenshot is a
visible gap, a fabricated one is worse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def save_window_png(window: Any, path: str | Path) -> str | None:
    """Save ``window`` as a PNG. Returns the path, or ``None`` if unavailable."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        window.root.update()
    except Exception:
        return None

    # Preferred: grab the window rectangle from the screen, which captures the
    # status panel as well as the board.
    try:
        from PIL import ImageGrab  # type: ignore

        root = window.root
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        image = ImageGrab.grab(
            bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())
        )
        image.save(target)
        return str(target)
    except Exception:
        pass

    # Fallback: PostScript of the canvas only. Loses the panel but proves the
    # belief map, which is the part the submission asks for.
    try:
        eps = target.with_suffix(".eps")
        window.canvas.postscript(file=str(eps), colormode="color")
        return str(eps)
    except Exception:
        return None
