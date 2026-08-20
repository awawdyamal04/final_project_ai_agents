"""Cross-team interop audit -- terms signature, game_uid, game_id (CORE,
BLOCKER for game_uid/game_id: two peers that derive different values cannot
join their artifacts or reports at all).

Before this audit this project implemented none of the three: the live
handshake gate is a *different*, book-mandated construction
(``config_sha256`` over the whole shared config, no nonce -- PDF p.127,
Appendix B) and ``--game-id`` is an operator-supplied CLI string, not a
sorted-pair derivation. ``police_thief.protocol.interop_ids`` adds the
interop-kit's constructions as small, additive, schema-agnostic functions
for use only when negotiating against a foreign implementation -- see that
module's docstring and docs/OPEN_QUESTIONS.md for why the book-mandated gate
is intentionally left untouched.

Fixture values embedded from copthief-league-protocol
``vectors/terms_signature.json`` and ``vectors/game_uid.json``.
"""

from __future__ import annotations

from police_thief.protocol.interop_ids import game_id, game_uid, terms_signature

TERMS = {
    "board_size": 7, "smell_grid_size": 5, "decay_per_step": 0.1,
    "emit_intensity": 0.9, "min_center_intensity": 0.5, "max_steps": 35,
    "barriers_max": 14, "setting": "Haifa", "hint_max_words": 15,
    "axis_origin_corner": "top-left", "axis_start_index": 0,
    "thief_start": [3, 3], "cop_start": [0, 0], "num_games": 1,
}
TERMS_NONCE = "a1a2a3a4b1b2b3b4c1c2c3c4d1d2d3d4"
TERMS_SIGNATURE = "80793141f22b6193b02a74d5955767ad1e24abbac172894358ec13622b85a04c"

EXPECTED_UID = "1e73c318-5b29-4a7b-1c60-ecb8286265f0"
EXPECTED_ID = "team-aleph-vs-team-bet"


def test_terms_signature_matches_vector():
    assert terms_signature(TERMS, TERMS_NONCE) == TERMS_SIGNATURE


def test_game_uid_matches_vector():
    assert game_uid(TERMS, "team-aleph", "team-bet") == EXPECTED_UID


def test_game_id_matches_vector():
    assert game_id("team-aleph", "team-bet") == EXPECTED_ID


def test_swapping_group_order_changes_neither_id():
    """Both peers derive one identical pair of ids with no round-trip and no
    convention to settle -- a peer that names itself first instead would
    produce a different id on each side of the same match."""
    assert game_uid(TERMS, "team-bet", "team-aleph") == EXPECTED_UID
    assert game_id("team-bet", "team-aleph") == EXPECTED_ID


def test_artifact_filenames_derive_from_game_id():
    """Book App. F table 20 grammar."""
    gid = game_id("team-aleph", "team-bet")
    assert f"declaration_{gid}.json" == "declaration_team-aleph-vs-team-bet.json"
    assert f"result_{gid}.json" == "result_team-aleph-vs-team-bet.json"
    assert f"config_{gid}_g01.json" == "config_team-aleph-vs-team-bet_g01.json"
    assert f"log_{gid}_g01.json" == "log_team-aleph-vs-team-bet_g01.json"


def test_a_self_named_id_would_diverge_across_peers():
    """The failure interop_ids.game_id exists to prevent: naming yourself
    first produces two different strings for the same match."""
    us_first = "-vs-".join(["team-bet", "team-aleph"])
    them_first = "-vs-".join(["team-aleph", "team-bet"])
    assert us_first != them_first
    assert game_id("team-bet", "team-aleph") == game_id("team-aleph", "team-bet")
