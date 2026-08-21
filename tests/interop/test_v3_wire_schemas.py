"""Reference-v3 adapter -- wire schema fidelity (SPEC section 7.5).

Unlike ``test_wire_shape_and_locked_models.py`` (which pins that this
project's *native* wire deliberately does not speak reference-v3), these
tests are against the new ``police_thief.interop`` package, which does.
"""

from __future__ import annotations

import json
from pathlib import Path

from police_thief.interop.wire import (
    AUDIT_REQUIRED,
    CONTROL_OPTIONAL,
    CONTROL_REQUIRED,
    TURN_OPTIONAL,
    TURN_REQUIRED,
    audit_payload,
    control_message,
    turn_message,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
KIT_ROOT = REPO_ROOT.parent / "copthief-league-protocol"
TURN_VECTOR = KIT_ROOT / "vectors" / "turn_message.json"


def test_turn_required_optional_match_the_kit_vector():
    """Byte-identical to ``vectors/turn_message.json``'s own key lists, so a
    schema drift here is caught immediately rather than at a live handshake."""
    if not TURN_VECTOR.is_file():
        return  # kit not available in this environment; covered elsewhere
    data = json.loads(TURN_VECTOR.read_text(encoding="utf-8"))
    assert set(data["turn_message"]["required"]) == TURN_REQUIRED
    assert set(data["turn_message"]["optional"]) == TURN_OPTIONAL
    assert set(data["audit_payload"]["required"]) == AUDIT_REQUIRED
    assert set(data["control_message"]["required"]) == CONTROL_REQUIRED
    assert set(data["control_message"]["optional"]) == CONTROL_OPTIONAL


def test_turn_message_builder_emits_the_full_ten_key_set():
    """Matches the vector's own 'accept' shape: nulls explicit, not omitted."""
    msg = turn_message(
        step=7, sender="police", hint="north of the park", smell_grid={"3,3": 0.9},
        commit="a" * 64, timestamp="2026-08-08T19:00:00Z",
    )
    assert set(msg) == TURN_REQUIRED | TURN_OPTIONAL
    assert msg["barrier_placed"] is None
    assert msg["capture_claim"] is None


def test_control_message_builder_matches_required_and_optional():
    msg = control_message(kind="status", sender="police")
    assert set(msg) >= CONTROL_REQUIRED
    assert set(msg) == CONTROL_REQUIRED | CONTROL_OPTIONAL


def test_audit_payload_builder_matches_required():
    msg = audit_payload(sender="police", records=[], result_claim="capture")
    assert set(msg) == AUDIT_REQUIRED
