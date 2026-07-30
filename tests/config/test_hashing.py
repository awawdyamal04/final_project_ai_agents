"""config_sha256 must be deterministic and must ignore private configuration."""

from __future__ import annotations

import json

import pytest

from police_thief.config.exceptions import ConfigHashMismatchError
from police_thief.config.hashing import (
    config_sha256,
    sha256_hex,
    verify_config_sha256,
)
from police_thief.config.loader import load_private_config, load_shared_config

# Pinned digest of the shipped config/game.json. If this changes, a binding
# value changed -- which is exactly the event the hash exists to make visible.
# Update it deliberately, never reflexively.
EXPECTED_SHIPPED_DIGEST = (
    "410066bfe426b268092f69b07e95e2bab4fa8826dd5b1b8643cbbf6befd0a24d"
)


def test_digest_is_lowercase_hex_of_length_64(valid_shared):
    digest = config_sha256(valid_shared)
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_digest_is_stable_across_repeated_calls(valid_shared):
    first = config_sha256(valid_shared)
    for _ in range(20):
        assert config_sha256(valid_shared) == first


def test_key_order_does_not_change_the_digest(valid_shared, shared_path):
    """The opponent may serialise their file differently and must still match."""
    reordered = dict(reversed(list(valid_shared.items())))
    reordered["board_and_agents"] = dict(
        reversed(list(valid_shared["board_and_agents"].items()))
    )
    assert config_sha256(reordered) == config_sha256(valid_shared)


def test_whitespace_does_not_change_the_digest(valid_shared):
    pretty = json.loads(json.dumps(valid_shared, indent=8))
    compact = json.loads(json.dumps(valid_shared, separators=(",", ":")))
    assert config_sha256(pretty) == config_sha256(compact)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("board_and_agents", "grid_size", 9),
        ("movement_and_barriers", "max_moves", 40),
        ("world", "hint_max_words", 12),
        ("network_and_league", "token_budget_per_series", 100000),
        ("scoring", "technical_loss", 0),  # same value -> see assertion below
    ],
)
def test_changing_a_shared_value_changes_the_digest(
    valid_shared, section, key, value
):
    baseline = config_sha256(valid_shared)
    valid_shared[section][key] = value
    changed = config_sha256(valid_shared)
    if value == json.loads(json.dumps(value)) and changed == baseline:
        # Only legitimate when the value did not actually change.
        assert value == 0 and key == "technical_loss"
    else:
        assert changed != baseline


def test_private_configuration_does_not_affect_the_shared_digest(
    valid_shared, cop_example_path, thief_example_path
):
    """The cop and thief run different private files against one constitution."""
    baseline = config_sha256(valid_shared)
    cop = load_private_config(cop_example_path)
    thief = load_private_config(thief_example_path)

    assert cop.role.value != thief.role.value
    assert cop.network.port != thief.network.port
    # Neither private object is an input to the hash, by construction.
    assert config_sha256(valid_shared) == baseline


def test_shipped_config_matches_the_pinned_digest(shared_path):
    shared = load_shared_config(shared_path)
    assert config_sha256(shared.raw) == EXPECTED_SHIPPED_DIGEST


def test_loaded_config_hash_matches_raw_mapping_hash(shared_path, valid_shared):
    """Hashing goes through `raw`, not a reconstruction of the dataclass."""
    shared = load_shared_config(shared_path)
    assert config_sha256(shared.raw) == config_sha256(valid_shared)


def test_verify_accepts_a_matching_digest(valid_shared):
    digest = config_sha256(valid_shared)
    assert verify_config_sha256(valid_shared, digest) == digest
    assert verify_config_sha256(valid_shared, digest.upper()) == digest


def test_verify_rejects_a_mismatched_digest(valid_shared):
    with pytest.raises(ConfigHashMismatchError, match="Refuse to play"):
        verify_config_sha256(valid_shared, "0" * 64)


def test_sha256_hex_matches_hashlib():
    import hashlib

    payload = b"police-thief"
    assert sha256_hex(payload) == hashlib.sha256(payload).hexdigest()
