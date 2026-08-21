"""Cross-team interop audit -- commit-reveal construction (CORE, BLOCKER).

The book v3.0.0 release publishes three mutually inconsistent commit
constructions (see docs/OPEN_QUESTIONS.md); the interop kit pins the
*reference* one -- ``SHA256(canonical_json(payload) + "|" + nonce)``, nonce
pipe-appended, never sealed as a key inside the hashed object -- as the CORE
cross-team form: an opponent's post-match audit re-hashes your revealed
records with this construction, so a different one fails every audit against
every conformant team even though each side's own self-check still passes.

Fixture values embedded from copthief-league-protocol
``vectors/commit_reveal.json`` (external interop kit data, not vendored
code). The payload schema itself is not an interop constraint (SPEC section
3) -- only the hash construction is -- so these vectors are checked directly
against this project's schema-agnostic ``pipe_nonce_commitment`` helper,
and separately against this project's own ``SealedRecord`` to prove the
production commit-reveal path uses the identical construction.
"""

from __future__ import annotations

import pytest

from police_thief.config.hashing import pipe_nonce_commitment
from police_thief.crypto.sealed import SealedRecord, commitment_for_mapping
from police_thief.domain.actions import Move
from police_thief.domain.enums import Direction, Role

VECTORS = [
    (
        {
            "step": 0, "type": "system_spec",
            "spec": {"os": "Linux", "cpu_cores": 4, "ram_gb": 16.0, "vram_gb": 0.0},
            "model": "cli-default", "code_version": "1.0",
            "group_name": "Example-Team", "sub_game_number": 1,
        },
        "0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        "69c9a786d18829990291cd0ffb768eacfa009011b0c89a6f4f32330551e2003e",
    ),
    (
        {
            "step": 1, "state": "grid=7x7;self=[4, 3];barriers=[]",
            "position": [4, 3], "move": "MOVE:S", "intent": "truth",
            "hint": "I keep to the main avenues.",
        },
        "112233445566778899aabbccddeeff00",
        "aa6420e2d3a907d6c140856caecbb351b4d5ad98e381549c28268669af378dcc",
    ),
    (
        {
            "step": 2, "state": "grid=7x7;self=[2, 4];barriers=[[1, 1]]",
            "position": [2, 4], "move": "MOVE:N", "intent": "lie",
            "hint": "אני ליד הכיכר 🙂",
        },
        "deadbeefcafef00dfeedface00c0ffee",
        "2caaeb0a7e656868b85166a9ebe34226bae4fdcb79cb7a0a23759121769d9338",
    ),
]


@pytest.mark.parametrize(("payload", "nonce", "expected"), VECTORS)
def test_pipe_nonce_commitment_matches_reference_form(payload, nonce, expected):
    """The construction itself, schema-agnostic (payload field names never
    need to match an opponent's -- only the formula does)."""
    assert pipe_nonce_commitment(payload, nonce) == expected


def test_divergent_forms_reference_is_the_one_this_project_now_builds():
    """The same sealed record under the release's three published
    constructions; only ``reference_form`` is the interop-kit's CORE form."""
    payload = {
        "step": 1, "state": "grid=7x7;self=[4, 3];barriers=[]",
        "position": [4, 3], "move": "MOVE:S", "intent": "truth",
        "hint": "I keep to the main avenues.",
    }
    nonce = "112233445566778899aabbccddeeff00"
    assert pipe_nonce_commitment(payload, nonce) == (
        "aa6420e2d3a907d6c140856caecbb351b4d5ad98e381549c28268669af378dcc"
    )


def _record(**overrides) -> SealedRecord:
    base = {
        "game_id": "team-aleph-vs-team-bet", "sub_game": 1, "turn": 1,
        "role": Role.POLICE, "state": "a" * 64, "action": Move(Direction.N),
        "hint": "north of the park", "intent": "truth", "nonce": "1" * 32,
    }
    base.update(overrides)
    return SealedRecord(**base)


def test_sealed_record_commitment_uses_the_reference_construction():
    """The production path: pop the nonce, hash the rest canonically,
    pipe-append the nonce -- matching ``pipe_nonce_commitment`` exactly for
    the same split, over this project's own (differently-named) schema."""
    record = _record()
    mapping = record.to_sealed_mapping()
    nonce = mapping.pop("nonce")
    assert record.commitment() == pipe_nonce_commitment(mapping, nonce)


def test_audit_recompute_uses_the_same_construction_as_seal():
    """What an opponent's audit does to our revealed records: pop nonce,
    recompute. Must equal what we sealed with, or our own audit of our own
    (self-consistent) history would already fail -- the same mechanism a
    real opponent's audit exercises across implementations."""
    record = _record(turn=7)
    revealed = record.with_nonce_disclosed()
    assert commitment_for_mapping(revealed) == record.commitment()


def test_nonce_is_pipe_appended_not_sealed_inside_the_object():
    """Root-cause regression: before this fix, ``commitment()`` hashed the
    nonce as an ordinary JSON key (the book's ch.5-listing form) instead of
    pipe-appending it outside the canonical object (the reference form) --
    self-consistent, and invisible until an opponent's audit re-hashed it."""
    record = _record()
    with_nonce_as_key = record.to_sealed_mapping()  # nonce included as a key
    from police_thief.config.canonical import canonical_json_bytes
    from police_thief.config.hashing import sha256_hex

    wrong_form = sha256_hex(canonical_json_bytes(with_nonce_as_key))
    assert record.commitment() != wrong_form
