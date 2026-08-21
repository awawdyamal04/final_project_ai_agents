"""Regression coverage for the capture-vs-timeout disagreement (urgent
sprint, Phase A): the live external run reported our side settling a
sub-game as ``capture`` while the reference kit settled the *same* sub-game
as ``timeout``. Code review of ``sparring/netplay.py``/``turnloop.py``
showed the kit's own historical fix for exactly this shape --
``terminal_message()``, a dedicated ``STAY`` record sent the moment an
outcome is locally decided, so a board-blind opponent is told rather than
left to wait out its budget. ``GameSessionV3`` had no equivalent: it kept
computing a brand-new strategy move every call, so the one message the
opponent was blocked on rode behind unrelated, avoidable work.

These tests pin the fixed contract directly, without a network: once
``outcome`` is set, ``take_turn()`` must stop moving the game forward and
must promptly hand back only the terminal record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.domain.enums import Role
from police_thief.interop.audit_adapter import seal_record
from police_thief.interop.game_receive import receive_turn
from police_thief.interop.game_session import GameSessionV3
from police_thief.interop.turn_validate import validate_turn_message
from police_thief.interop.wire import turn_message

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


def _clock() -> str:
    return datetime.now(UTC).isoformat()


def _sessions(cfg):
    cop = GameSessionV3(role=Role.POLICE, config=cfg, sub_game_number=1, clock_stamp=_clock)
    thief = GameSessionV3(role=Role.THIEF, config=cfg, sub_game_number=1, clock_stamp=_clock)
    return cop, thief


def test_terminal_message_is_none_when_nothing_is_owed():
    """A side with no pending answer and no self-detected survival has
    nothing left to say -- exactly the reference's own ``terminal_message``
    contract (returns ``None`` rather than resealing empty state)."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    cop, _ = _sessions(cfg)
    cop.outcome = "capture"  # simulate: outcome known, nothing pending
    assert cop.take_turn() is None


def test_terminal_message_is_a_stay_not_a_new_move():
    """Once outcome is set, take_turn must not consult the strategy or
    change position -- only reseal the pending answer as a dedicated record.
    This is the actual regression: the old code kept calling
    ``strategy.choose``/``apply_action`` here, delaying the one message the
    opponent was blocked on behind unrelated work."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    _, thief = _sessions(cfg)
    position_before = thief.state.position
    step_before = thief.step
    thief.pending_answer = {"claim": [0, 0], "caught": True}
    thief.outcome = "capture"

    msg = thief.take_turn()

    assert msg is not None
    assert msg["step"] == step_before + 1  # a real step, so delivery applies it
    assert thief.state.position == position_before  # no movement computed
    assert msg["barrier_placed"] is None
    assert msg["capture_claim"] is None
    assert msg["claim_response"] == {"claim": [0, 0], "caught": True}
    validate_turn_message(msg)


def test_pending_concession_survives_to_delivery_without_extra_moves():
    """Reproduces the disagreement end to end, in-process, deterministically
    (no strategy RNG involved): a barrier lands exactly on the thief's own
    cell (rule 46), the thief self-detects the concession on receipt, and
    the *very next* call must be the terminal record -- delivering it must
    bring the cop to the same outcome the thief already knows, with no
    round where our side has decided ``capture`` but sent the opponent
    nothing new to act on (the exact shape of the live disagreement: our
    side reported capture, the kit reported timeout).
    """
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    cop, thief = _sessions(cfg)
    own_cell = list(thief.state.position.as_list())

    record = seal_record(
        {"step": 1, "sub_game": 1, "role": "police", "position": own_cell, "action": "barrier"}
    )
    barrier_msg = turn_message(
        step=1, sender="police", hint="", smell_grid={}, commit=record["commit"],
        timestamp=_clock(), barrier_placed=own_cell, capture_claim=None,
        claim_response=None, win_claim=None,
    )

    receive_turn(thief, barrier_msg)
    assert thief.outcome == "capture"
    assert thief.pending_answer is not None

    # The thief now knows it is caught; the very next call must be the
    # terminal record, not a further computed move.
    position_before = thief.state.position
    final = thief.take_turn()
    assert final is not None
    assert final["claim_response"] == {"claim": own_cell, "caught": True}
    assert thief.state.position == position_before

    receive_turn(cop, final)
    assert cop.outcome == thief.outcome == "capture"


def test_a_barrier_concession_survives_a_missed_claim_in_the_same_message():
    """Phase H: a cop's barrier and its ``capture_claim`` guess can ride the
    same message. If the barrier already conceded the game (rule 46 -- a
    fact only the thief can see) but the claim names a DIFFERENT cell (a
    miss, ``caught=False``), the missed-claim answer must not overwrite the
    true concession. The live shape this reproduces: our side silently sent
    a ``caught=False`` answer instead of the true concession, so the cop --
    which cannot see the board -- never learned it had won and settled the
    sub-game as a timeout it had actually taken by barrier.
    """
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    cop, thief = _sessions(cfg)
    own_cell = list(thief.state.position.as_list())
    missed_guess = [c + 1 for c in own_cell]  # deliberately NOT the thief's cell

    record = seal_record(
        {"step": 1, "sub_game": 1, "role": "police", "position": own_cell, "action": "barrier"}
    )
    msg = turn_message(
        step=1, sender="police", hint="", smell_grid={}, commit=record["commit"],
        timestamp=_clock(), barrier_placed=own_cell, capture_claim=missed_guess,
        claim_response=None, win_claim=None,
    )

    receive_turn(thief, msg)
    assert thief.outcome == "capture"
    # The true concession -- caught at OUR OWN cell -- not the missed guess.
    assert thief.pending_answer == {"claim": own_cell, "caught": True}

    final = thief.take_turn()
    assert final["claim_response"] == {"claim": own_cell, "caught": True}

    receive_turn(cop, final)
    assert cop.outcome == "capture"  # the cop actually learns it won
