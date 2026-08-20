"""End-to-end (in-process) coverage of the before/after match hooks."""

from __future__ import annotations

from police_thief.domain.enums import Role
from police_thief.learning.integration import prepare_adaptive_strategy, record_match_outcome
from police_thief.learning.store import load_global_profile, load_opponent_profile, opponent_key
from police_thief.peer.run import _build_parser
from police_thief.strategy.heuristics import CopStrategy
from police_thief.strategy.thief_risk import RiskThiefStrategy


def test_unknown_group_id_uses_global_profile_only(learning_dir):
    strategy, model, lines = prepare_adaptive_strategy(Role.THIEF, learning_dir, None, seed=1)
    assert isinstance(strategy, RiskThiefStrategy)
    assert any("none yet" in line or "unknown" in line for line in lines)


def test_known_opponent_after_one_match_is_reused_next_time(learning_dir):
    _, model, _ = prepare_adaptive_strategy(Role.POLICE, learning_dir, "Team B", seed=1)
    record_match_outcome(
        role=Role.POLICE, learning_dir=learning_dir, declared_opponent_name="Team B",
        opponent_model=model, turns_played=30, exit_status="MATCH COMPLETE",
    )
    _, _, lines = prepare_adaptive_strategy(Role.POLICE, learning_dir, "Team B", seed=1)
    assert any("1 prior games" in line for line in lines)


def test_failed_match_does_not_poison_profile(learning_dir):
    _, model, _ = prepare_adaptive_strategy(Role.POLICE, learning_dir, "Team C", seed=1)
    status = record_match_outcome(
        role=Role.POLICE, learning_dir=learning_dir, declared_opponent_name="Team C",
        opponent_model=model, turns_played=2, exit_status="TECHNICAL LOSS",
    )
    assert "skipped" in status

    key = opponent_key("Team C")
    assert load_opponent_profile(key, learning_dir).games_seen == 0
    assert load_global_profile(learning_dir).games_seen == 0


def test_aborted_match_zero_turns_does_not_poison_profile(learning_dir):
    _, model, _ = prepare_adaptive_strategy(Role.POLICE, learning_dir, "Team D", seed=1)
    record_match_outcome(
        role=Role.POLICE, learning_dir=learning_dir, declared_opponent_name="Team D",
        opponent_model=model, turns_played=0, exit_status="MATCH COMPLETE",
    )
    assert load_global_profile(learning_dir).games_seen == 0


def test_learning_disabled_is_the_default_and_leaves_strategy_selection_untouched():
    """No --adaptive-learning -> peer/run.py never calls into this package,
    so production strategy loading (heuristics.load_strategy) is unaffected."""
    args = _build_parser().parse_args(["--private", "config/cop.toml.example"])
    assert args.adaptive_learning is False


def test_record_match_outcome_never_raises_on_a_bad_learning_dir(tmp_path):
    """A learning-store problem must never surface as a match failure."""
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x", encoding="utf-8")  # a file, not a directory
    model = RiskThiefStrategy().opponent_model
    status = record_match_outcome(
        role=Role.POLICE, learning_dir=blocked / "sub", declared_opponent_name="Team E",
        opponent_model=model, turns_played=30, exit_status="MATCH COMPLETE",
    )
    assert status.startswith("learning update: not saved")


def test_adaptive_cop_never_becomes_the_experimental_belief_cop(learning_dir):
    """The sprint's own safety rule: the cop adaptation stays on the
    production CopStrategy class, never silently swaps to BeliefCopStrategy."""
    strategy, _, _ = prepare_adaptive_strategy(Role.POLICE, learning_dir, "Team B", seed=1)
    assert isinstance(strategy, CopStrategy)
