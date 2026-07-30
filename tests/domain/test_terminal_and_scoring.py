"""Terminal conditions and scoring."""

from __future__ import annotations

import pytest

from police_thief.config.loader import build_shared_config
from police_thief.domain.actions import Move
from police_thief.domain.enums import (
    CaptureReason,
    Direction,
    Role,
    TerminalReason,
)
from police_thief.domain.exceptions import GameAlreadyFinishedError
from police_thief.domain.scoring import (
    apply_tie_rule,
    calculate_score,
)
from police_thief.domain.terminal import (
    capture,
    evaluate_move_ceiling,
    evaluate_survival,
    max_moves_reached,
    survival,
    technical_loss,
)
from police_thief.domain.transition import apply_action


# ----------------------------------------------------------------------
# Terminal conditions
# ----------------------------------------------------------------------


def test_survival_fires_at_the_configured_threshold(shared_config):
    threshold = shared_config.movement_and_barriers.survival_threshold
    assert evaluate_survival(threshold - 1, shared_config) is None
    result = evaluate_survival(threshold, shared_config)
    assert result is not None
    assert result.reason is TerminalReason.SURVIVAL
    assert result.winner is Role.THIEF


def test_survival_threshold_is_read_from_config_not_hard_coded(valid_shared):
    valid_shared["movement_and_barriers"]["survival_threshold"] = 40
    valid_shared["movement_and_barriers"]["max_moves"] = 40
    config = build_shared_config(valid_shared)
    assert evaluate_survival(35, config) is None
    assert evaluate_survival(40, config) is not None


def test_move_ceiling_fires_at_max_moves(shared_config):
    ceiling = shared_config.movement_and_barriers.max_moves
    assert evaluate_move_ceiling(ceiling - 1, shared_config) is None
    result = evaluate_move_ceiling(ceiling, shared_config)
    assert result is not None
    assert result.reason is TerminalReason.MAX_MOVES_REACHED


def test_terminal_results_are_deterministic(shared_config):
    threshold = shared_config.movement_and_barriers.survival_threshold
    first = evaluate_survival(threshold, shared_config)
    for _ in range(10):
        assert evaluate_survival(threshold, shared_config) == first


def test_technical_loss_has_no_winner():
    result = technical_loss(7)
    assert result.winner is None
    assert result.reason is TerminalReason.TECHNICAL_LOSS


def test_capture_and_survival_classification():
    assert capture(3, CaptureReason.BARRIER_ON_THIEF).is_capture
    assert survival(35).is_survival
    assert max_moves_reached(35).is_survival
    assert not technical_loss(3).is_capture


def test_no_action_is_possible_after_a_terminal_state(cop_state, shared_config):
    finished = cop_state.finished(survival(35))
    assert finished.is_finished
    with pytest.raises(GameAlreadyFinishedError, match="no further action"):
        apply_action(finished, Move(Direction.S), shared_config)


def test_terminal_result_serialises(shared_config):
    payload = capture(4, CaptureReason.THIEF_HAS_NO_LEGAL_MOVE).to_dict()
    assert payload == {
        "reason": "capture",
        "turn": 4,
        "winner": "police",
        "capture_reason": "thief_has_no_legal_move",
    }


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------


def test_capture_scores_come_from_config(shared_config):
    score = calculate_score(capture(5, CaptureReason.COP_LANDED_ON_THIEF), shared_config)
    assert score.cop == shared_config.scoring.capture_cop == 20
    assert score.thief == shared_config.scoring.capture_thief == 5
    assert score.reason is TerminalReason.CAPTURE


def test_survival_scores_come_from_config(shared_config):
    score = calculate_score(survival(35), shared_config)
    assert score.cop == shared_config.scoring.survival_cop == 5
    assert score.thief == shared_config.scoring.survival_thief == 10


def test_max_moves_is_scored_as_survival(shared_config):
    """The thief evaded for the whole sub-game, which is what survival rewards."""
    assert calculate_score(max_moves_reached(35), shared_config).thief == (
        shared_config.scoring.survival_thief
    )


def test_technical_loss_zeroes_both_sides(shared_config):
    score = calculate_score(technical_loss(9), shared_config)
    assert score.cop == score.thief == shared_config.scoring.technical_loss == 0
    assert score.total == 0


def test_scoring_is_asymmetric_as_the_pdf_intends(shared_config):
    """Capture is the cop's best outcome; survival is the thief's."""
    cap = calculate_score(capture(5, CaptureReason.COP_LANDED_ON_THIEF), shared_config)
    surv = calculate_score(survival(35), shared_config)
    assert cap.cop > surv.cop
    assert surv.thief > cap.thief


def test_score_for_role(shared_config):
    score = calculate_score(capture(5, CaptureReason.BARRIER_ON_THIEF), shared_config)
    assert score.for_role(Role.POLICE) == 20
    assert score.for_role(Role.THIEF) == 5


def test_scoring_uses_no_hard_coded_values(valid_shared):
    """A raised NEGOTIABLE config must flow through; FIXED stays enforced.

    scoring.* are all FIXED, so this proves the *mechanism* reads config by
    altering the one scoring key Appendix F does not bind (D-3).
    """
    valid_shared["scoring"]["technical_loss"] = 0
    config = build_shared_config(valid_shared)
    assert calculate_score(technical_loss(1), config).cop == 0


def test_scoring_rejects_nothing_it_should_score(shared_config):
    """Every TerminalReason has a score."""
    for reason in TerminalReason:
        from police_thief.domain.terminal import TerminalResult

        result = TerminalResult(reason=reason, turn=1)
        assert calculate_score(result, shared_config) is not None


# ----------------------------------------------------------------------
# Tie rule -- match level, not sub-game level
# ----------------------------------------------------------------------


def test_tie_rule_awards_tie_score_to_both_sides(shared_config):
    """Ch. 9, PDF p. 87: over the accumulated score of ALL sub-games."""
    match = apply_tie_rule(45, 45, shared_config)
    assert match.tied
    assert match.cop == match.thief == shared_config.scoring.tie_score == 2


def test_tie_rule_leaves_unequal_totals_alone(shared_config):
    match = apply_tie_rule(60, 30, shared_config)
    assert not match.tied
    assert (match.cop, match.thief) == (60, 30)


def test_tie_is_not_a_sub_game_terminal_reason():
    """It is a match-level rule; sub-games end in capture, survival or loss."""
    assert "tie" not in {reason.value for reason in TerminalReason}
