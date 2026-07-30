"""Canonical JSON must be deterministic, or every audit is a coin flip."""

from __future__ import annotations

import pytest

from police_thief.config.canonical import canonical_json_bytes, canonical_json_text
from police_thief.config.exceptions import CanonicalSerialisationError


def test_key_order_does_not_affect_output():
    a = {"b": 1, "a": 2, "c": 3}
    b = {"c": 3, "a": 2, "b": 1}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_nested_key_order_does_not_affect_output():
    a = {"outer": {"z": [1, {"q": 1, "p": 2}], "a": True}}
    b = {"outer": {"a": True, "z": [1, {"p": 2, "q": 1}]}}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_array_order_is_preserved():
    """Arrays are ordered data; sorting them would change meaning."""
    assert canonical_json_text([3, 1, 2]) == "[3,1,2]"
    assert canonical_json_text([1, 2, 3]) != canonical_json_text([3, 2, 1])


def test_output_has_no_whitespace():
    text = canonical_json_text({"a": 1, "b": [1, 2], "c": {"d": 3}})
    assert text == '{"a":1,"b":[1,2],"c":{"d":3}}'
    assert " " not in text
    assert "\n" not in text


def test_source_whitespace_does_not_reach_output():
    import json

    spaced = json.loads('{\n   "a" :  1,\n   "b"  : 2\n}')
    compact = json.loads('{"a":1,"b":2}')
    assert canonical_json_bytes(spaced) == canonical_json_bytes(compact)


def test_repeated_calls_are_stable():
    value = {"x": [1, {"y": "z"}], "a": None, "b": False}
    first = canonical_json_bytes(value)
    for _ in range(50):
        assert canonical_json_bytes(value) == first


def test_bytes_are_utf8_encoded_text():
    value = {"map_area": "New York"}
    assert canonical_json_bytes(value) == canonical_json_text(value).encode("utf-8")


def test_non_ascii_is_deterministic_utf8():
    """Hebrew round-trips as real UTF-8 characters, not escapes."""
    value = {"note": "שוטר וגנב"}
    raw = canonical_json_bytes(value)
    assert raw.decode("utf-8") == '{"note":"שוטר וגנב"}'
    assert canonical_json_bytes(value) == raw


def test_scalars_are_stable():
    assert canonical_json_text(True) == "true"
    assert canonical_json_text(False) == "false"
    assert canonical_json_text(None) == "null"
    assert canonical_json_text(0) == "0"
    assert canonical_json_text(-1) == "-1"
    assert canonical_json_text("") == '""'


def test_bool_is_not_coerced_to_int():
    assert canonical_json_text({"a": True}) != canonical_json_text({"a": 1})


@pytest.mark.parametrize(
    "value",
    [
        {1: "int key"},
        {None: "none key"},
        {"s": {1, 2}},
        {"b": b"bytes"},
        {"t": (1, 2)},
        {"o": object()},
        float("nan"),
        float("inf"),
        float("-inf"),
        {"nested": [1, [2, {"deep": {3.0: "bad key"}}]]},
    ],
)
def test_unsupported_values_are_rejected(value):
    with pytest.raises(CanonicalSerialisationError):
        canonical_json_text(value)


def test_rejection_message_names_the_path():
    with pytest.raises(CanonicalSerialisationError) as exc:
        canonical_json_text({"outer": {"inner": [0, object()]}})
    assert "$.outer.inner[1]" in str(exc.value)
