"""Reference-v3 adapter -- ``subtractive_chebyshev_v1`` scent (SPEC section
5), byte-verified against ``vectors/pheromone.json``'s own emit/decay
fixtures. Distinct from ``test_pheromone_self_test.py``, which pins that
this project's *native* Gaussian model is a different, undocumented third
variant -- this file is about the new adapter-local reimplementation, which
must be exact.
"""

from __future__ import annotations

from police_thief.domain.coordinates import Coordinate
from police_thief.interop.scent_v3 import decay_v3, emit_v3, wire_key_to_cell


def test_emit_reproduces_the_centre_vector():
    field = emit_v3(center=(3, 3), intensity=0.9, grid_size=5, board_size=7)
    assert field["3,3"] == 0.9
    assert field["2,2"] == 0.6
    assert field["1,1"] == 0.3
    assert field["2,3"] == 0.6  # orthogonal neighbour, distance 1


def test_emit_clips_a_corner_field_to_the_board():
    field = emit_v3(center=(0, 0), intensity=0.9, grid_size=5, board_size=7)
    assert field == {
        "0,0": 0.9, "0,1": 0.6, "0,2": 0.3,
        "1,0": 0.6, "1,1": 0.6, "1,2": 0.3,
        "2,0": 0.3, "2,1": 0.3, "2,2": 0.3,
    }


def test_zero_and_negative_values_never_cross_the_wire():
    field = emit_v3(center=(3, 3), intensity=0.9, grid_size=5, board_size=7)
    assert all(v > 0.0 for v in field.values())


def test_decay_matches_the_vector():
    before = {"3,3": 0.9, "3,4": 0.6, "3,5": 0.3}
    after = decay_v3(before, decay=0.1)
    assert after == {"3,3": 0.8, "3,4": 0.5, "3,5": 0.2}


def test_decay_clamps_to_the_floor_and_drops_the_cell():
    after = decay_v3({"1,1": 0.05}, decay=0.1)
    assert "1,1" not in after


def test_wire_key_round_trips_to_a_coordinate():
    assert wire_key_to_cell("3,4") == Coordinate(3, 4)
