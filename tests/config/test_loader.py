"""Loading: parsing, duplicate keys, closed schema, and file errors."""

from __future__ import annotations

import json

import pytest

from police_thief.config.exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    DuplicateConfigKeyError,
    InvalidConfigTypeError,
    MissingConfigFieldError,
    UnknownConfigFieldError,
)
from police_thief.config.loader import (
    build_shared_config,
    load_shared_config,
    parse_shared_mapping,
)


def test_valid_complete_configuration_loads(shared_path):
    shared = load_shared_config(shared_path)
    assert shared.schema_version == "1.2"
    assert shared.board_and_agents.num_agents == 2
    assert shared.scoring.capture_cop == 20
    assert shared.pheromones.pheromone_decay == pytest.approx(0.10)
    assert shared.source_path == shared_path


def test_missing_file_raises_not_found(tmp_path):
    with pytest.raises(ConfigFileNotFoundError, match="no configuration file"):
        load_shared_config(tmp_path / "absent.json")


def test_malformed_json_raises_parse_error(tmp_path):
    path = tmp_path / "game.json"
    path.write_text('{"schema_version": "1.2",,}', encoding="utf-8")
    with pytest.raises(ConfigParseError, match="not valid JSON"):
        load_shared_config(path)


def test_truncated_json_raises_parse_error(tmp_path):
    path = tmp_path / "game.json"
    path.write_text('{"schema_version": "1.2"', encoding="utf-8")
    with pytest.raises(ConfigParseError):
        load_shared_config(path)


def test_non_object_json_is_rejected():
    with pytest.raises(InvalidConfigTypeError, match="must be a JSON object"):
        parse_shared_mapping("[1, 2, 3]")


def test_invalid_utf8_raises_parse_error(tmp_path):
    path = tmp_path / "game.json"
    path.write_bytes(b'{"schema_version": "\xff\xfe"}')
    with pytest.raises(ConfigParseError, match="not valid UTF-8"):
        load_shared_config(path)


# --------------------------------------------------------------------------
# Duplicate keys -- json.load would silently keep the last one
# --------------------------------------------------------------------------


def test_duplicate_key_is_rejected():
    text = '{"max_moves": 50, "max_moves": 60}'
    # Confirm the standard parser really does swallow this, so the test is
    # guarding a live hazard rather than a hypothetical one.
    assert json.loads(text) == {"max_moves": 60}
    with pytest.raises(DuplicateConfigKeyError, match="duplicate key"):
        parse_shared_mapping(text)


def test_duplicate_key_in_nested_object_is_rejected():
    text = """
    {
      "board_and_agents": {"grid_size": 7, "grid_size": 9}
    }
    """
    with pytest.raises(DuplicateConfigKeyError, match="grid_size"):
        parse_shared_mapping(text)


def test_duplicate_key_in_shipped_shape_is_rejected(valid_shared):
    body = json.dumps(valid_shared)
    injected = body.replace('"grid_size": 7', '"grid_size": 7, "grid_size": 5', 1)
    with pytest.raises(DuplicateConfigKeyError):
        parse_shared_mapping(injected)


def test_same_key_in_different_objects_is_fine():
    """Only repetition within one object is ambiguous."""
    mapping = parse_shared_mapping('{"a": {"x": 1}, "b": {"x": 2}}')
    assert mapping == {"a": {"x": 1}, "b": {"x": 2}}


# --------------------------------------------------------------------------
# Closed schema
# --------------------------------------------------------------------------


def test_unknown_top_level_field_is_rejected(valid_shared):
    valid_shared["extra_section"] = {}
    with pytest.raises(UnknownConfigFieldError, match="extra_section"):
        build_shared_config(valid_shared)


def test_unknown_nested_field_is_rejected(valid_shared):
    valid_shared["board_and_agents"]["grid_height"] = 7
    with pytest.raises(UnknownConfigFieldError, match="grid_height"):
        build_shared_config(valid_shared)


def test_renamed_field_is_rejected_not_defaulted(valid_shared):
    """Field names are fixed and binding (PDF p. 130).

    A renamed key must fail loudly. If it were ignored and the old name
    defaulted, two peers could compute different physics while both believing
    they had agreed.
    """
    board = valid_shared["board_and_agents"]
    board["gridSize"] = board.pop("grid_size")
    with pytest.raises((UnknownConfigFieldError, MissingConfigFieldError)):
        build_shared_config(valid_shared)


def test_missing_top_level_section_is_rejected(valid_shared):
    del valid_shared["pheromones"]
    with pytest.raises(MissingConfigFieldError, match="pheromones"):
        build_shared_config(valid_shared)


def test_missing_nested_field_is_rejected(valid_shared):
    del valid_shared["scoring"]["tie_score"]
    with pytest.raises(MissingConfigFieldError, match="tie_score"):
        build_shared_config(valid_shared)


def test_missing_structural_field_is_rejected(valid_shared):
    del valid_shared["schema_version"]
    with pytest.raises(MissingConfigFieldError, match="schema_version"):
        build_shared_config(valid_shared)


@pytest.mark.parametrize(
    ("section", "key", "bad"),
    [
        ("board_and_agents", "grid_size", "7"),
        ("board_and_agents", "grid_size", 7.5),
        ("board_and_agents", "num_agents", True),
        ("world", "map_area", 5),
        ("world", "hint_max_words", "15"),
        ("movement_and_barriers", "move_set", "N,S,E,W,STAY"),
        ("scoring", "capture_cop", "20"),
        ("network_and_league", "num_games", "6"),
        ("rate_limiter_gatekeeper", "queue_depth", None),
    ],
)
def test_wrong_type_is_rejected(valid_shared, section, key, bad):
    valid_shared[section][key] = bad
    with pytest.raises(InvalidConfigTypeError):
        build_shared_config(valid_shared)


def test_bool_is_not_accepted_where_an_int_belongs(valid_shared):
    """JSON `true` is not 1; accepting it would silently change the board."""
    valid_shared["board_and_agents"]["grid_size"] = True
    with pytest.raises(InvalidConfigTypeError, match="got bool"):
        build_shared_config(valid_shared)


def test_integer_is_accepted_where_a_float_belongs(valid_shared):
    """JSON writes 1 for 1.0; the widening is safe and must not be an error."""
    valid_shared["pheromones"]["pheromone_center_intensity"] = 0.9
    valid_shared["pheromones"]["pheromone_decay"] = 0.1
    shared = build_shared_config(valid_shared)
    assert isinstance(shared.pheromones.pheromone_center_intensity, float)


def test_section_that_is_not_an_object_is_rejected(valid_shared):
    valid_shared["scoring"] = [1, 2, 3]
    with pytest.raises(InvalidConfigTypeError, match="must be an object"):
        build_shared_config(valid_shared)


@pytest.mark.parametrize("bad", [[3], [3, 3, 3], "3,3", [3, "3"], [3, True]])
def test_malformed_coordinate_is_rejected(valid_shared, bad):
    valid_shared["board_and_agents"]["thief_start"] = bad
    with pytest.raises(InvalidConfigTypeError):
        build_shared_config(valid_shared)


def test_loaded_object_is_frozen(shared_path):
    """A config that can change after validation is a config whose hash lies."""
    import dataclasses

    shared = load_shared_config(shared_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        shared.schema_version = "9.9"  # type: ignore[misc]
