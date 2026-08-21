"""Reference-v3 adapter -- inbound TurnMessage structural validation.

Every case mirrors ``vectors/turn_message.json``'s own ``validation`` list.
"""

from __future__ import annotations

import pytest

from police_thief.interop.turn_validate import validate_turn_message

VALID = {
    "step": 7, "sender": "police", "hint": "north of the park",
    "smell_grid": {"3,3": 0.9, "3,4": 0.5, "4,3": 0.5},
    "commit": "a" * 64, "timestamp": "2026-08-08T19:00:00Z",
    "barrier_placed": [5, 6], "capture_claim": None,
    "claim_response": None, "win_claim": None,
}


def _tweak(**overrides):
    msg = dict(VALID)
    msg.update(overrides)
    return msg


def test_accepts_the_full_ten_key_set():
    validate_turn_message(_tweak())


def test_accepts_and_ignores_unknown_field():
    validate_turn_message(_tweak(unknown_field={"anything": 1}))


def test_rejects_empty_timestamp():
    with pytest.raises(Exception, match="timestamp"):
        validate_turn_message(_tweak(timestamp=""))


def test_rejects_missing_commit():
    msg = _tweak()
    del msg["commit"]
    with pytest.raises(Exception, match="missing required"):
        validate_turn_message(msg)


def test_rejects_uppercase_hex_commit():
    with pytest.raises(Exception, match="commit"):
        validate_turn_message(_tweak(commit="A" * 64))


def test_rejects_short_commit():
    with pytest.raises(Exception, match="commit"):
        validate_turn_message(_tweak(commit="a" * 63))


def test_rejects_stringified_smell_grid_value():
    with pytest.raises(Exception, match="smell_grid"):
        validate_turn_message(_tweak(smell_grid={"3,3": "0.9"}))


def test_rejects_negative_step():
    with pytest.raises(Exception, match="step"):
        validate_turn_message(_tweak(step=-1))


def test_rejects_bool_step():
    with pytest.raises(Exception, match="step"):
        validate_turn_message(_tweak(step=True))


def test_rejects_unknown_sender():
    with pytest.raises(Exception, match="sender"):
        validate_turn_message(_tweak(sender="referee"))


def test_rejects_non_dict_message():
    with pytest.raises(Exception, match="object"):
        validate_turn_message("not a dict")
