"""Reference-v3 adapter -- capture-claim self-verification (SPEC section
3.1: answer vs. concession), built on the same domain functions the native
E-21/E-22 path already uses.
"""

from __future__ import annotations

from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.domain.enums import Role
from police_thief.domain.state import LocalState
from police_thief.interop.capture_v3 import answer_landed_claim, self_report_concession

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


def _thief_state(cfg):
    return LocalState.initial(Role.THIEF, cfg)


def test_answer_confirms_a_true_landed_claim():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = _thief_state(cfg)
    claim = list(thief.position.as_list())
    answer = answer_landed_claim(claim, thief)
    assert answer == {"claim": claim, "caught": True}


def test_answer_denies_a_false_landed_claim():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = _thief_state(cfg)
    wrong_cell = [thief.position.row + 5, thief.position.col]
    answer = answer_landed_claim(wrong_cell, thief)
    assert answer == {"claim": wrong_cell, "caught": False}


def test_answer_is_none_when_no_claim_present():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = _thief_state(cfg)
    assert answer_landed_claim(None, thief) is None


def test_self_report_concession_on_barrier_landed_on_own_cell():
    """Rule 46: a barrier placed on the thief's own cell -- a fact only the
    thief can see, so it must say so out loud."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = _thief_state(cfg)
    own_cell = thief.position.as_tuple()
    concession = self_report_concession(thief, cfg, barrier_just_placed=own_cell)
    assert concession == {"claim": list(own_cell), "caught": True}


def test_self_report_concession_is_none_when_not_captured():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = _thief_state(cfg)
    elsewhere = (thief.position.row + 1, thief.position.col + 1)
    assert self_report_concession(thief, cfg, barrier_just_placed=elsewhere) is None


def test_self_report_concession_distinct_from_answer_semantics():
    """A concession names the thief's OWN final cell, never the cell the
    cop claimed -- the two settle capture identically but corroborate
    differently at audit (SPEC section 3.1)."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = _thief_state(cfg)
    own_cell = thief.position.as_tuple()
    concession = self_report_concession(thief, cfg, barrier_just_placed=own_cell)
    answer = answer_landed_claim(list(own_cell), thief)
    assert concession["claim"] == answer["claim"]  # same cell, different provenance
