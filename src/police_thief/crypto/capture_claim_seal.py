"""Cryptographic binding for capture_claim records.

Reuses the existing canonical-JSON + SHA-256 commitment primitive
(``config/canonical.py``, ``config/hashing.py`) -- the same one
``crypto/sealed.py`` uses for the per-turn commit -- rather than inventing a
second cryptographic system (prd.md Sec 14.10, a design decision [B], not an
assignment mandate: E-21/E-22 require *that* a claim be signed and
verifiable, not any particular scheme).

Not built on ``SealedRecord`` itself: that record's field set is shaped for
an ``action``/``hint``/``intent`` turn, not a claim/verdict. Reusing the
*primitive* (canonical JSON -> SHA-256) rather than the *dataclass* keeps
this module honest about what is actually shared.
"""

from __future__ import annotations

import hmac

from police_thief.config.canonical import canonical_json_bytes
from police_thief.config.hashing import sha256_hex

_SCHEMA = "1.0"


def seal_claim(
    *,
    game_id: str,
    sub_game: int,
    turn: int,
    claimant_role: str,
    claim_kind: str,
    claim_id: str,
) -> str:
    """Commitment for a cop's ``CAPTURE_CLAIM``."""
    mapping = {
        "v": _SCHEMA,
        "kind": "capture_claim",
        "game_id": game_id,
        "sub_game": sub_game,
        "turn": turn,
        "claimant_role": claimant_role,
        "claim_kind": claim_kind,
        "claim_id": claim_id,
    }
    return sha256_hex(canonical_json_bytes(mapping))


def seal_response(
    *,
    game_id: str,
    sub_game: int,
    turn: int,
    responder_role: str,
    verdict: str,
    claim_id: str,
) -> str:
    """Commitment for a thief's ``CAPTURE_CLAIM_RESPONSE``."""
    mapping = {
        "v": _SCHEMA,
        "kind": "capture_claim_response",
        "game_id": game_id,
        "sub_game": sub_game,
        "turn": turn,
        "responder_role": responder_role,
        "verdict": verdict,
        "claim_id": claim_id,
    }
    return sha256_hex(canonical_json_bytes(mapping))


def commitments_match(left: str, right: str) -> bool:
    """Constant-time comparison, matching ``crypto/coordinator.py``'s own
    convention for commitment verification."""
    return hmac.compare_digest(left, right)
