"""Reference-v3 adapter -- negotiation (SPEC sections 4, 7, 7.2, 7.3).

Every refusal code SPAR-N00..N10 that ``verify_greeting`` can raise, plus
the one rule that governs half of them: omission never refuses, in either
direction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from police_thief.config.loader import load_shared_config
from police_thief.interop.exceptions import Refused
from police_thief.interop.negotiation import build_greeting, to_wire, verify_greeting

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


@pytest.fixture
def cfg():
    return load_shared_config(SHARED_CONFIG_PATH)


def _pair(cfg, **kw2):
    ours = build_greeting(cfg, group_id="group-aaa", role="police", sub_game_number=1)
    kw2.setdefault("sub_game_number", 1)
    theirs = build_greeting(cfg, group_id="group-bbb", role="thief", **kw2)
    return ours, theirs


def test_agrees_on_matching_terms(cfg):
    ours, theirs = _pair(cfg)
    agreed = verify_greeting(ours, to_wire(theirs))
    assert agreed.opponent_group == "group-bbb"
    assert agreed.opponent_role == "thief"
    assert agreed.game_id == "group-aaa-vs-group-bbb"


def test_n00_greeting_not_an_object(cfg):
    ours, _ = _pair(cfg)
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, "not a dict")
    assert exc.value.code == "SPAR-N00"


def test_n01_terms_absent(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    del raw["terms"]
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N01"


def test_n02_terms_incomplete(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    del raw["terms"]["max_steps"]
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N02"


def test_n03_terms_value_mismatch(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    raw["terms"]["max_steps"] = raw["terms"]["max_steps"] + 1
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N03"


def test_n04_signature_does_not_verify(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    raw["signature"] = "0" * 64
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N04"


def test_n04_no_nonce(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    del raw["nonce"]
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N04"


def test_n06_sub_game_mismatch(cfg):
    ours, theirs = _pair(cfg, sub_game_number=2)
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, to_wire(theirs))
    assert exc.value.code == "SPAR-N06"


def test_n07_role_collision(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    raw["role"] = "police"
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N07"


def test_n08_no_group_id(cfg):
    ours, theirs = _pair(cfg)
    raw = to_wire(theirs)
    del raw["group_id"]
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, raw)
    assert exc.value.code == "SPAR-N08"


def test_locked_model_omission_never_refuses(cfg):
    """The unmodified reference peer declares none of these -- a guard that
    fail-fasts on silence would forfeit the game to itself."""
    ours = build_greeting(
        cfg, group_id="group-aaa", role="police", sub_game_number=1,
        locks={"scent_model": "deadbeef"},
    )
    _, theirs = _pair(cfg)
    agreed = verify_greeting(ours, to_wire(theirs))  # theirs declares nothing
    assert agreed is not None


def test_locked_model_mismatch_refuses_only_when_both_declare(cfg):
    ours = build_greeting(
        cfg, group_id="group-aaa", role="police", sub_game_number=1,
        locks={"scent_model": "aaaa"},
    )
    theirs = build_greeting(
        cfg, group_id="group-bbb", role="thief", sub_game_number=1,
        locks={"scent_model": "bbbb"},
    )
    with pytest.raises(Refused) as exc:
        verify_greeting(ours, to_wire(theirs))
    assert exc.value.code == "SPAR-N05"
