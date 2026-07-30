"""Sealed record, nonce, and commitment."""

from __future__ import annotations

import pytest

from police_thief.crypto.exceptions import SealedRecordValidationError
from police_thief.crypto.nonce import (
    NONCE_HEX_LENGTH,
    NonceGuard,
    generate_nonce,
    is_well_formed,
)
from police_thief.crypto.sealed import (
    SEALED_KEYS,
    SEALED_SCHEMA_VERSION,
    SealedRecord,
    commitment_for_mapping,
    sealed_record_from_mapping,
    validate_sealed_mapping,
)
from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role

FIXED_NONCE = "0" * 32
"""A fixed, non-secret test value. Real nonces never appear in test output."""


def record(**overrides) -> SealedRecord:
    base = dict(
        game_id="g1",
        sub_game=1,
        turn=3,
        role=Role.POLICE,
        state="a" * 64,
        action=Move(Direction.N),
        hint="heading for the bright lights",
        intent="truth",
        nonce=FIXED_NONCE,
    )
    base.update(overrides)
    return SealedRecord(**base)


# ----------------------------------------------------------------------
# Nonce
# ----------------------------------------------------------------------


def test_nonce_uses_secrets_not_random():
    """random's Mersenne Twister state is recoverable from its output."""
    import police_thief.crypto.nonce as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "import secrets" in source
    assert "import random" not in source
    assert "secrets.token_hex" in source


def test_nonce_format_is_lowercase_hex_of_fixed_length():
    for _ in range(50):
        nonce = generate_nonce()
        assert len(nonce) == NONCE_HEX_LENGTH == 32
        assert nonce == nonce.lower()
        assert is_well_formed(nonce)


def test_nonces_are_distinct_across_many_samples():
    samples = {generate_nonce() for _ in range(2000)}
    assert len(samples) == 2000


@pytest.mark.parametrize(
    "bad", ["", "abc", "A" * 32, "g" * 32, "0" * 31, "0" * 33, None, 12345]
)
def test_malformed_nonces_are_rejected(bad):
    assert not is_well_formed(bad)


def test_guard_never_issues_the_same_nonce_twice():
    guard = NonceGuard()
    issued = {guard.issue() for _ in range(500)}
    assert len(issued) == 500
    assert len(guard) == 500
    for nonce in issued:
        assert guard.has_used(nonce)


def test_guard_remembers_an_abandoned_nonce():
    """An abandoned turn's nonce must never be issued again."""
    guard = NonceGuard()
    guard.remember(FIXED_NONCE)
    assert guard.has_used(FIXED_NONCE)


# ----------------------------------------------------------------------
# Sealed record schema
# ----------------------------------------------------------------------


def test_sealed_key_set_is_closed_and_complete():
    assert set(record().to_sealed_mapping()) == set(SEALED_KEYS)
    assert SEALED_KEYS == {
        "v", "game_id", "sub_game", "turn", "role",
        "state", "action", "hint", "intent", "nonce",
    }


def test_sealed_record_carries_no_timestamp():
    """Two machines have two clocks; a timestamp would break byte-identity."""
    mapping = record().to_sealed_mapping()
    for key in mapping:
        assert "time" not in key.lower()
        assert "date" not in key.lower()


def test_sealed_record_carries_no_global_state():
    mapping = record().to_sealed_mapping()
    for banned in (
        "opponent_position", "opponent_cell", "board", "board_state",
        "global_state", "thief_position", "cop_position",
    ):
        assert banned not in mapping


def test_state_field_is_a_hash_not_a_position():
    """It binds the commitment to a position without disclosing one."""
    mapping = record().to_sealed_mapping()
    assert isinstance(mapping["state"], str)
    assert len(mapping["state"]) == 64


def test_valid_mapping_round_trips():
    original = record()
    restored = sealed_record_from_mapping(original.to_sealed_mapping())
    assert restored == original
    assert restored.commitment() == original.commitment()


def test_unknown_sealed_field_is_rejected():
    mapping = record().to_sealed_mapping()
    mapping["extra"] = 1
    with pytest.raises(SealedRecordValidationError, match="unknown sealed field"):
        validate_sealed_mapping(mapping)


@pytest.mark.parametrize("field", sorted(SEALED_KEYS))
def test_missing_sealed_field_is_rejected(field):
    mapping = record().to_sealed_mapping()
    del mapping[field]
    with pytest.raises(SealedRecordValidationError):
        validate_sealed_mapping(mapping)


def test_unsupported_schema_version_is_rejected():
    mapping = record().to_sealed_mapping()
    mapping["v"] = "9.9"
    with pytest.raises(SealedRecordValidationError, match="unsupported sealed"):
        validate_sealed_mapping(mapping)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("game_id", ""),
        ("game_id", 5),
        ("turn", -1),
        ("turn", "3"),
        ("turn", True),
        ("sub_game", -1),
        ("role", "referee"),
        ("intent", "maybe"),
        ("state", 5),
        ("hint", 5),
    ],
)
def test_invalid_sealed_values_are_rejected(field, bad):
    mapping = record().to_sealed_mapping()
    mapping[field] = bad
    with pytest.raises(SealedRecordValidationError):
        validate_sealed_mapping(mapping)


def test_invalid_action_is_rejected():
    from police_thief.protocol.exceptions import ProtocolValidationError

    mapping = record().to_sealed_mapping()
    mapping["action"] = {"v": 1, "kind": "teleport"}
    with pytest.raises((SealedRecordValidationError, ProtocolValidationError)):
        validate_sealed_mapping(mapping)


def test_bad_nonce_is_rejected():
    mapping = record().to_sealed_mapping()
    mapping["nonce"] = "not-a-nonce"
    with pytest.raises(SealedRecordValidationError, match="nonce"):
        validate_sealed_mapping(mapping)


def test_nonce_may_be_absent_when_not_required():
    """The per-turn reveal omits it (E-18)."""
    mapping = record().to_reveal_mapping()
    assert "nonce" not in mapping
    validate_sealed_mapping(mapping, require_nonce=False)


# ----------------------------------------------------------------------
# Commitment
# ----------------------------------------------------------------------


def test_commitment_is_lowercase_hex_sha256():
    digest = record().commitment()
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_commitment_is_deterministic():
    first = record().commitment()
    for _ in range(20):
        assert record().commitment() == first


def test_known_digest_fixture():
    """Pinned so an accidental schema change fails loudly."""
    assert record().commitment() == (
        "f7a7972f974e0b90c2f1e68cb6c51bd12585c236df2af20354fef0becd464e0a"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nonce", "1" * 32),
        ("action", Move(Direction.S)),
        ("turn", 4),
        ("role", Role.THIEF),
        ("game_id", "g2"),
        ("sub_game", 2),
        ("state", "b" * 64),
        ("hint", "different words entirely"),
        ("intent", "lie"),
    ],
)
def test_changing_any_sealed_field_changes_the_commitment(field, value):
    assert record().commitment() != record(**{field: value}).commitment()


def test_same_action_with_a_different_nonce_differs():
    """Without this the small move space would be a lookup table."""
    a = record(nonce="a" * 32).commitment()
    b = record(nonce="b" * 32).commitment()
    assert a != b


def test_barrier_action_commits_distinctly():
    a = record(action=PlaceBarrier(Coordinate(1, 2))).commitment()
    b = record(action=PlaceBarrier(Coordinate(2, 1))).commitment()
    assert a != b


def test_source_key_order_does_not_change_the_commitment():
    """Canonical serialisation: both peers must hash byte-identical input."""
    mapping = record().to_sealed_mapping()
    reordered = dict(reversed(list(mapping.items())))
    assert commitment_for_mapping(reordered) == record().commitment()


def test_action_is_not_recoverable_from_the_commitment():
    """The digest reveals nothing about its content (PDF p. 51)."""
    digest = record().commitment()
    for token in ("N", "move", "STAY", "police", "bright lights", FIXED_NONCE):
        assert token not in digest


def test_commitment_binds_game_turn_role_and_action():
    """The four bindings that stop a commitment being replayed elsewhere."""
    base = record().commitment()
    assert record(game_id="other").commitment() != base
    assert record(turn=99).commitment() != base
    assert record(role=Role.THIEF).commitment() != base
    assert record(action=Move(Direction.STAY)).commitment() != base


def test_commitment_uses_the_single_canonical_helper():
    import police_thief.crypto.sealed as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "canonical_json_bytes" in source
    assert "sort_keys" not in source  # not reimplemented
    assert "hashlib" not in source    # goes through config.hashing
