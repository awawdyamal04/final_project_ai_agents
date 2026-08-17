"""The turn banner: pure text/colour logic, no Tk.

Split out of ``gui/live.py`` (Q-19, D-44) because this is the one piece of
rendering logic worth testing without a display -- getting it wrong is
exactly what produced the original Q-19 finding, a finished match still
reading "YOUR TURN" under ``--hold``. Kept Tk-free on purpose: this project's
CI/sandbox has no display and no ``tkinter`` module at all.
"""

from __future__ import annotations

from police_thief.gui.view_model import LiveView

GREEN = "#2ecc71"
GREY = "#555b6b"


def banner_for(view: LiveView) -> tuple[str, str]:
    """The turn banner's text and background colour for one view.

    A set ``final_status`` means the peer has shut down (``run.py``'s
    ``finally`` block sets it right before the last frame is published) and
    is checked first and unconditionally, so a finished match can never be
    drawn as if it were still this peer's turn -- regardless of whatever
    ``phase``/``peer_state`` the snapshot happened to freeze on.
    """
    if view.final_status is not None:
        return "GAME COMPLETE", GREY
    acting = view.phase in ("choosing action", "idle", "turn complete")
    locked = not acting and view.peer_state != "ready"
    return ("LOCKED", GREY) if locked else ("YOUR TURN", GREEN)
