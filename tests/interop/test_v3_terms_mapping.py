"""Reference-v3 adapter -- the TERMS_KEYS <-> ``config/game.json`` mapping.

Resolves what ``protocol/interop_ids.py``'s docstring and
docs/OPEN_QUESTIONS.md Q-21 point 3 previously left unresolved: which of
this project's own config keys correspond 1:1 to the kit's flat 14-key
``TERMS_KEYS`` (``sparring/config.py``). Found by reading that file
directly; pinned here so a future config field rename cannot silently break
the mapping without a failing test.
"""

from __future__ import annotations

from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.interop.wire import DEFAULT_MIN_CENTER_INTENSITY, terms_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"

#: The kit's own flat 14-key set (``sparring/config.py``'s ``TERMS_KEYS``),
#: reproduced here as a literal so this test is self-contained even when the
#: external kit is not checked out alongside this repo.
KIT_TERMS_KEYS = frozenset({
    "board_size", "smell_grid_size", "decay_per_step", "emit_intensity",
    "min_center_intensity", "max_steps", "barriers_max", "setting",
    "hint_max_words", "axis_origin_corner", "axis_start_index",
    "thief_start", "cop_start", "num_games",
})


def test_terms_from_config_is_exactly_the_kit_s_flat_key_set():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    terms = terms_from_config(cfg)
    assert set(terms) == KIT_TERMS_KEYS


def test_every_value_is_canonically_serialisable():
    """Coordinates must be lists, not tuples -- ``config/models.py``'s
    ``Coord = tuple[int, int]`` would otherwise reach the canonical
    serializer and be rejected (it accepts dict/list/str/int/float/bool/None
    only, see ``config/canonical.py``)."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    terms = terms_from_config(cfg)
    assert isinstance(terms["thief_start"], list)
    assert isinstance(terms["cop_start"], list)
    from police_thief.config.canonical import canonical_json_bytes

    canonical_json_bytes(terms)  # raises on anything unsupported


def test_values_are_pulled_from_the_real_shared_config_not_hardcoded():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    terms = terms_from_config(cfg)
    assert terms["board_size"] == cfg.board_and_agents.grid_size
    assert terms["smell_grid_size"] == cfg.pheromones.pheromone_grid_size
    assert terms["decay_per_step"] == cfg.pheromones.pheromone_decay
    assert terms["emit_intensity"] == cfg.pheromones.pheromone_center_intensity
    assert terms["max_steps"] == cfg.movement_and_barriers.max_moves
    assert terms["barriers_max"] == cfg.movement_and_barriers.max_barriers
    assert terms["setting"] == cfg.world.map_area
    assert terms["hint_max_words"] == cfg.world.hint_max_words
    assert terms["num_games"] == cfg.network_and_league.num_games


def test_min_center_intensity_is_the_documented_adapter_only_default():
    """This project's own scent model has no lower floor at all -- see
    ``domain/scent.py`` -- so this one term has no config counterpart and is
    a fixed adapter constant, per the kit's own default
    (``sparring/rules/scent.py``)."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    terms = terms_from_config(cfg)
    assert terms["min_center_intensity"] == DEFAULT_MIN_CENTER_INTENSITY == 0.5
