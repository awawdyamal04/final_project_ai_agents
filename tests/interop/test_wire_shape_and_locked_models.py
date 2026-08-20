"""Cross-team interop audit -- wire shape (PROMOTED tool surface + turn
message shape) and locked-model declarations (SPEC section 7).

These two rows are **documented gaps, not fixed**, per the task's own
constraint ("do NOT rewrite our protocol to match blindly"): this project's
wire shape is a deliberate, self-consistent, book-first design (an explicit
COMMIT -> COMMIT_ACK -> REVEAL -> REVEAL_ACK -> ... FINAL_REVEAL state
machine over ``MessageType``) built and tested across many prior phases. The
interop kit's ``reference-v3`` wire shape is a *different*, simpler
per-half-turn push (``negotiate`` / ``receive_turn`` / ``submit_audit`` /
``receive_control``, one combined ``TurnMessage`` per half-turn carrying
``step, sender, hint, smell_grid, commit, timestamp``). Per SPEC section 7,
``wire_shape`` is itself a *negotiated, lockable choice* between two teams,
not a universal requirement -- so the fix for a real cross-team match is to
**declare** the deviation (a ``wire_shape`` locked-model doc, SPEC section
7) before playing, not to rewrite this project's already-tested protocol.

These tests pin the CURRENT state as a fact so a future change is a
deliberate, reviewed decision rather than a silent drift either way.
"""

from __future__ import annotations

from police_thief.protocol.messages import _PAYLOAD_SCHEMAS, MessageType

REFERENCE_V3_TOOLS = {"negotiate", "receive_turn", "submit_audit", "receive_control"}
REFERENCE_V3_TURN_MESSAGE_REQUIRED = {
    "step", "sender", "hint", "smell_grid", "commit", "timestamp",
}


def test_this_project_does_not_expose_the_reference_v3_tool_surface():
    """FAIL against ``vectors/turn_message.json``'s tool list, by design: no
    ``negotiate``/``receive_turn``/``submit_audit``/``receive_control`` tool
    names exist in this project's closed ``MessageType`` set."""
    our_message_types = {m.value for m in MessageType}
    assert our_message_types.isdisjoint(REFERENCE_V3_TOOLS)


def test_no_single_message_carries_the_reference_v3_turn_shape():
    """This project splits a half-turn across COMMIT (digest only) and
    REVEAL (action + hint, no nonce) -- neither carries ``smell_grid``, and
    neither alone carries the full reference-v3 required key set."""
    commit_keys = set(_PAYLOAD_SCHEMAS[MessageType.COMMIT])
    reveal_keys = set(_PAYLOAD_SCHEMAS[MessageType.REVEAL])
    assert not commit_keys >= REFERENCE_V3_TURN_MESSAGE_REQUIRED
    assert not reveal_keys >= REFERENCE_V3_TURN_MESSAGE_REQUIRED


def test_scent_is_never_transmitted_on_this_project_s_wire():
    """No payload schema anywhere carries a scent/smell field -- each peer
    keeps its own trail locally and never receives the opponent's, closer in
    spirit to the book's ``multiplicative_book_v1`` (``transmitted: false``,
    no receiver-side pass) than to reference-v3's mandatory wire grid."""
    for schema in _PAYLOAD_SCHEMAS.values():
        assert "smell_grid" not in schema


def test_no_locked_model_registry_exists():
    """N/A, not FAIL: SPEC section 7's refusal rule is 'refuse only when
    BOTH peers declare a family and the hashes differ' -- omission never
    refuses, in either direction. A peer (like this one) that declares no
    ``scent_model_sha256``/``wire_shape_sha256``/etc. plays the unmodified
    reference peer exactly as today; there is nothing here to be
    incompatible with until this project chooses to lock something."""
    import police_thief.protocol as protocol_pkg

    assert not hasattr(protocol_pkg, "locked_model")
    assert not hasattr(protocol_pkg, "LOCK_FAMILIES")
