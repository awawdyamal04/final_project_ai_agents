"""Live per-peer GUI.

Displays only what a peer may legally see. The boundary is the
:class:`~police_thief.gui.view_model.LiveView` type, which has no field for the
opponent's position -- so the renderer cannot draw one, and a leak cannot be
introduced by editing drawing code.

Distinct from :mod:`police_thief.replay`, which *may* show global truth because
it runs offline after the final reveal. No module here imports it.
"""

from police_thief.gui.view_model import LiveView, snapshot

__all__ = ["LiveView", "snapshot"]
