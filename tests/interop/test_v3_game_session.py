"""Reference-v3 adapter -- ``GameSessionV3`` end-to-end: two real sessions
(the shipped ``CopStrategy``/``RiskThiefStrategy``, real ``LocalState``,
real ``BeliefMap``) played against each other in-process, with no network,
proving the turn loop, capture/survival adjudication and the audit re-hash
all agree on both sides.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.domain.enums import Role
from police_thief.interop.audit_adapter import verify_audit
from police_thief.interop.game_receive import receive_turn
from police_thief.interop.game_session import GameSessionV3
from police_thief.interop.turn_validate import validate_turn_message
from police_thief.interop.wire import audit_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


def _clock() -> str:
    return datetime.now(UTC).isoformat()


def _send(session, other) -> None:
    """One half-turn, mirroring ``orchestrator._send_next``: ``take_turn``
    legitimately returns ``None`` once outcome is decided and this side has
    nothing left to say (:mod:`terminal_v3`) -- there is then nothing to
    validate or deliver."""
    msg = session.take_turn()
    if msg is None:
        return
    validate_turn_message(msg)
    receive_turn(other, msg)


def _play_full_series(cfg):
    cop = GameSessionV3(role=Role.POLICE, config=cfg, sub_game_number=1, clock_stamp=_clock)
    thief = GameSessionV3(role=Role.THIEF, config=cfg, sub_game_number=1, clock_stamp=_clock)
    max_rounds = cfg.movement_and_barriers.max_moves

    _send(thief, cop)
    rounds = 0
    while (cop.outcome is None or thief.outcome is None) and rounds < max_rounds + 2:
        rounds += 1
        _send(cop, thief)
        _send(thief, cop)
    return cop, thief


def test_thief_opens_the_sub_game():
    """The reference implementation's own observed turn order -- caused a
    real historical deadlock when unmatched (SPEC, ``sparring/turnloop.py``
    module docstring)."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    thief = GameSessionV3(role=Role.THIEF, config=cfg, sub_game_number=1, clock_stamp=_clock)
    cop = GameSessionV3(role=Role.POLICE, config=cfg, sub_game_number=1, clock_stamp=_clock)
    assert thief.opens is True
    assert cop.opens is False


def test_a_full_series_ends_with_both_sides_agreeing_on_the_outcome():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    cop, thief = _play_full_series(cfg)
    assert cop.outcome is not None
    assert cop.outcome == thief.outcome


def test_every_outbound_message_validates_structurally():
    """Already asserted turn-by-turn above via ``validate_turn_message`` --
    this test exists to name that guarantee explicitly."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    _play_full_series(cfg)  # would have raised TurnValidationError otherwise


def test_mutual_audit_cross_verifies_with_zero_mismatches():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    cop, thief = _play_full_series(cfg)

    cop_payload = audit_payload(sender="police", records=cop.records, result_claim=cop.outcome)
    thief_payload = audit_payload(sender="thief", records=thief.records, result_claim=thief.outcome)

    thief_side_check = verify_audit(thief_payload, played=cop.inbox.played)
    cop_side_check = verify_audit(cop_payload, played=thief.inbox.played)

    assert thief_side_check.verified, thief_side_check.mismatches
    assert cop_side_check.verified, cop_side_check.mismatches


def test_a_tampered_reveal_is_caught_by_the_opponent_side():
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    cop, thief = _play_full_series(cfg)
    tampered = audit_payload(sender="police", records=cop.records, result_claim=cop.outcome)
    tampered["records"][0]["nonce"] = "0" * 32  # forges the first step's reveal
    result = verify_audit(tampered, played=thief.inbox.played)
    assert not result.verified
