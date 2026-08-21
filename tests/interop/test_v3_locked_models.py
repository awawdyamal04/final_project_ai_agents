"""Phase E: locked-model declarations. Pins ``declarable_locks()`` against
the exact ``sha256`` values registered in the kit's own
``vectors/locked_model.json`` for the four models this adapter actually
implements -- transcribed once, verified here, so a future edit that
silently drifts the doc (and therefore the hash) fails a test instead of a
real handshake.
"""

from __future__ import annotations

from police_thief.interop.locked_models import declarable_locks
from police_thief.interop.negotiation import LOCK_FAMILIES, build_greeting, to_wire

# Copied from copthief-league-protocol/vectors/locked_model.json's
# "registered" entries -- the subtractive_chebyshev_v1/reference-v3/belief/
# none rows only (the models this adapter actually implements).
_REGISTERED = {
    "scent_model": "81ebee59640e80eae8ca9ee5f86abd26e7edf5cdbb27d15925cb6ee45ca6ddf4",
    "wire_shape": "229ae6487a418c3fcb6da9be404de2f2533c288ebc228811bff6dedc4164d6f7",
    "info_mode": "020947daeeb3f73494af9b04201326791742c7184085456e3517d21981ee1202",
    "smell_binding": "f471af61ad178939e528b1346f996ed52f46fb06c9f420d913bf26dec524c5a6",
}

# The OTHER model registered per family -- what this adapter must NOT
# accidentally reproduce (would mean we mislabelled a doc as ours).
_NOT_OURS = {
    "scent_model": "934c220d5bf62acaa3297c6c9d723ea954c220260b02292ca17f6d5daef9f4d9",
    "wire_shape": "f3fc1d424c461a02a1db9490306318c46043501bc1da1bfcb1b56ff9bc76f376",
    "info_mode": "be93ca76794f1bf638572f532bba32e08131737397febf377395abe7333c5489",
    "smell_binding": "7992141d219704e56a10d0c263c0272755760d0556d3271eeff3950bb366309b",
}


def test_declares_exactly_the_four_families():
    locks = declarable_locks()
    assert set(locks) == set(LOCK_FAMILIES)


def test_every_declared_hash_matches_the_registered_vector():
    locks = declarable_locks()
    for family, expected in _REGISTERED.items():
        assert locks[family] == expected, f"{family}: hash drifted from the registered doc"


def test_no_declared_hash_matches_the_model_we_do_not_implement():
    locks = declarable_locks()
    for family, other in _NOT_OURS.items():
        assert locks[family] != other


def test_declarable_locks_is_stable_across_calls():
    """No timestamps, nonces, or randomness leak into a locked-model doc --
    it must hash identically every time, unlike a greeting's own nonce."""
    assert declarable_locks() == declarable_locks()


def test_locks_flow_into_the_wire_greeting():
    from pathlib import Path

    from police_thief.config.loader import load_shared_config

    cfg = load_shared_config(Path(__file__).resolve().parents[2] / "config" / "game.json")
    greeting = build_greeting(
        cfg, group_id="group-aaa", role="police", sub_game_number=1, locks=declarable_locks()
    )
    wire = to_wire(greeting)
    for family, expected in _REGISTERED.items():
        assert wire[f"{family}_sha256"] == expected
