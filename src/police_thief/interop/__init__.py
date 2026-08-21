"""Additive reference-v3 compatibility surface (copthief-league-protocol kit).

**This package never replaces, deletes or rewrites the native protocol.**
Everything under ``police_thief.peer``/``police_thief.protocol`` continues to
run exactly as before; this package only *adds* four extra FastMCP tools
(``negotiate``, ``receive_turn``, ``submit_audit``, ``receive_control``) that
let a foreign peer speaking ``wire_shape: reference-v3`` (SPEC section 7.5)
play against this project's real strategies and domain logic.

Every construction reused here (canonical JSON, the pipe-nonce commit,
``terms_signature``/``game_uid``/``game_id``) is the same production code the
native protocol and ``tests/interop`` already exercise -- see
``protocol/interop_ids.py`` and ``config/hashing.py``. Nothing in this
package hand-rolls a hash.

See ``mount_reference_v3`` in :mod:`police_thief.interop.reference_v3` for
the single integration point a CLI needs.
"""

from __future__ import annotations

from police_thief.interop.reference_v3 import mount_reference_v3

__all__ = ["mount_reference_v3"]
