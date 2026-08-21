"""Locked-model declarations this adapter can safely send (Phase E, SPEC
section 7).

Declares ONLY the four families/models this adapter implements
byte-exactly, using the doc dicts registered in the kit's own
``vectors/locked_model.json`` -- transcribed here, not re-derived by
guesswork, and cross-checked (``tests/interop/test_v3_locked_models.py``)
against the exact registered ``sha256`` values, so a transcription slip
fails a test rather than a real handshake. The ``subtractive_chebyshev_v1``
example grid is *not* transcribed -- it is generated with this project's
own byte-verified :func:`~police_thief.interop.scent_v3.emit_v3`/
:func:`~police_thief.interop.scent_v3.decay_v3`, so that doc is
self-verifying rather than copied.

Declares:
  * ``scent_model``    -> ``subtractive_chebyshev_v1`` (our only scent
    model; verified against ``vectors/pheromone.json`` in the earlier
    interop audit).
  * ``wire_shape``     -> ``reference-v3`` (the only shape this adapter
    speaks).
  * ``info_mode``      -> ``belief`` (the belief-map strategy never reads
    the rival's true position -- E-8/E-9's own structural guarantee).
  * ``smell_binding``  -> ``none`` (the sealed record payload never
    includes ``smell_grid`` -- see ``game_session.take_turn`` -- so the
    transmitted field is exactly what the registered ``none`` doc
    describes: unauthenticated).

Nothing here declares ``multiplicative_book_v1``, ``bookletter-v3``,
``exact``, or ``commit_grid_v1`` -- this adapter does not implement any of
them, and SPEC section 7's own rule (omission never refuses) means simply
not sending a hash for a family we cannot honestly claim is always safe.
"""

from __future__ import annotations

import hashlib
from typing import Any

from police_thief.config.canonical import canonical_json_text
from police_thief.interop.scent_v3 import decay_v3, emit_v3

_WIRE_SHAPE_DOC: dict[str, Any] = {
    "family": "wire_shape", "name": "reference-v3",
    "params": {
        "tools": ["negotiate", "receive_turn", "submit_audit", "receive_control"],
        "messages_per_half_turn": 1, "smell_grid_on_wire": True,
        "move_revealed": "at_audit", "replicated_engines": False,
        "phases": "all four of book ch.5, with Reveal deferred to the audit boundary",
        "rival_position_computable_live": False,
    },
    "example": {
        "note": "one turn message per half-turn; the move is sealed, the field is sent",
        "turn_message_keys": ["step", "commit", "hint", "smell_grid", "barrier_placed"],
    },
}

_INFO_MODE_DOC: dict[str, Any] = {
    "family": "info_mode", "name": "belief",
    "params": {
        "rival_position_in_observation": False,
        "sources": ["own_state", "rival_scent", "hints"],
        "enforcement": (
            "structural under wire_shape reference-v3 (the rival's position never "
            "crosses the wire); an honor term under bookletter-v3, where the wire "
            "carries it and only the brain's restraint withholds it"
        ),
        "artifact_provable": {
            "mismatch": True, "violation": False,
            "why": (
                "a mismatch is provable from the two negotiate records; a violation is "
                "not, because a decision record does not disclose which information "
                "produced it"
            ),
        },
    },
    "example": {
        "note": "the observation space the brain is entitled to read",
        "observation_keys": ["self", "barriers", "smell_grid", "hint"],
    },
}

_SMELL_BINDING_DOC: dict[str, Any] = {
    "family": "smell_binding", "name": "none",
    "params": {},
    "example": {
        "note": (
            "the default and the whole of today's wire: the transmitted grid is "
            "unauthenticated. Registered so that `unbound` is a state a peer can "
            "declare rather than a silence it cannot distinguish from ignorance."
        ),
        "sealed_record_keys_added": [],
    },
}


def _scent_doc() -> dict[str, Any]:
    emit_field = emit_v3((3, 3), 0.9, 5, 7)
    return {
        "family": "scent_model", "name": "subtractive_chebyshev_v1",
        "params": {
            "field_size": 5, "emit_intensity": 0.9, "min_center_intensity": 0.5,
            "distance": "chebyshev", "falloff": "linear",
            "falloff_step": "emit_intensity / (field_size // 2 + 1)",
            "decay": "subtractive", "decay_per_step": 0.1,
            "update": "tau' = round(max(0, tau - decay_per_step), 3)",
            "rounding_decimals": 3, "clamp": [0.0, None],
            "cadence": "per_full_turn", "order": "deposit_then_decay",
            "receiver_side_decay": True, "initial_field": "empty", "transmitted": True,
        },
        "example": {
            "note": "emit at the centre of a 7x7 board, then one decay",
            "emit_center": [3, 3],
            "emit_field": emit_field,
            "after_one_decay": decay_v3(emit_field, 0.1),
        },
    }


def _hash(doc: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_text(doc).encode("utf-8")).hexdigest()


def declarable_locks() -> dict[str, str]:
    """The four hashes this adapter can honestly declare, keyed by family
    -- pass straight into :func:`~police_thief.interop.negotiation.
    build_greeting`'s ``locks`` argument."""
    return {
        "scent_model": _hash(_scent_doc()),
        "wire_shape": _hash(_WIRE_SHAPE_DOC),
        "info_mode": _hash(_INFO_MODE_DOC),
        "smell_binding": _hash(_SMELL_BINDING_DOC),
    }
