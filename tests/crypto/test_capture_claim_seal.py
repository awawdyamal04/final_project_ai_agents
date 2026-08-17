"""Cryptographic sealing for capture_claim (E-21, E-22): OUR design decision
to reuse the existing canonical-JSON + SHA-256 primitive, not a new scheme."""

from __future__ import annotations

from police_thief.crypto.capture_claim_seal import (
    commitments_match,
    seal_claim,
    seal_response,
)

CLAIM_KWARGS = {
    "game_id": "g1", "sub_game": 1, "turn": 5,
    "claimant_role": "police", "claim_kind": "barrier_on_thief", "claim_id": "c1",
}
RESPONSE_KWARGS = {
    "game_id": "g1", "sub_game": 1, "turn": 5,
    "responder_role": "thief", "verdict": "confirm", "claim_id": "c1",
}


def test_claim_commitment_is_lowercase_hex_sha256():
    digest = seal_claim(**CLAIM_KWARGS)
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_response_commitment_is_lowercase_hex_sha256():
    digest = seal_response(**RESPONSE_KWARGS)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_claim_commitment_is_deterministic():
    first = seal_claim(**CLAIM_KWARGS)
    for _ in range(10):
        assert seal_claim(**CLAIM_KWARGS) == first


def test_response_commitment_is_deterministic():
    first = seal_response(**RESPONSE_KWARGS)
    for _ in range(10):
        assert seal_response(**RESPONSE_KWARGS) == first


def test_claim_and_response_commitments_never_collide():
    """Different ``kind`` tags in the sealed mapping -- a claim's commitment
    can never be replayed as a response's, or vice versa."""
    claim_digest = seal_claim(**CLAIM_KWARGS)
    same_fields_as_response = seal_response(
        game_id="g1", sub_game=1, turn=5,
        responder_role="police", verdict="barrier_on_thief", claim_id="c1",
    )
    assert claim_digest != same_fields_as_response


def test_changing_any_claim_field_changes_the_commitment():
    base = seal_claim(**CLAIM_KWARGS)
    for field, value in (
        ("game_id", "g2"), ("sub_game", 2), ("turn", 6),
        ("claimant_role", "thief"), ("claim_kind", "landed"), ("claim_id", "c2"),
    ):
        changed = dict(CLAIM_KWARGS)
        changed[field] = value
        assert seal_claim(**changed) != base


def test_changing_any_response_field_changes_the_commitment():
    base = seal_response(**RESPONSE_KWARGS)
    for field, value in (
        ("game_id", "g2"), ("sub_game", 2), ("turn", 6),
        ("responder_role", "police"), ("verdict", "deny"), ("claim_id", "c2"),
    ):
        changed = dict(RESPONSE_KWARGS)
        changed[field] = value
        assert seal_response(**changed) != base


def test_source_key_order_does_not_change_the_commitment():
    """Canonical serialisation -- both peers must hash byte-identical input."""
    assert seal_claim(**CLAIM_KWARGS) == seal_claim(
        **{k: CLAIM_KWARGS[k] for k in reversed(list(CLAIM_KWARGS))}
    )


def test_commitments_match_is_constant_time_equality():
    a = seal_claim(**CLAIM_KWARGS)
    b = seal_claim(**CLAIM_KWARGS)
    c = seal_claim(**{**CLAIM_KWARGS, "claim_id": "different"})
    assert commitments_match(a, b)
    assert not commitments_match(a, c)


def test_commitment_uses_the_canonical_helper_not_a_new_scheme():
    import police_thief.crypto.capture_claim_seal as module

    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "canonical_json_bytes" in source
    assert "sha256_hex" in source
    assert "hashlib" not in source
