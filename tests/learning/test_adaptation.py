"""Bounded adaptation: hard clipping, low-confidence staying near baseline,
and deterministic behaviour for a fixed seed."""

from __future__ import annotations

from police_thief.learning import adaptation
from police_thief.learning.profile import LearningProfile
from police_thief.strategy.thief_risk import RiskThiefStrategy
from police_thief.strategy.weights import ThiefWeights


def _saturated_profile(**overrides) -> LearningProfile:
    profile = LearningProfile(sample_count=100, games_seen=100)
    bias = overrides.pop("direction_bias", {"N": 1.0, "S": 0.0, "E": 0.0, "W": 0.0})
    profile.direction_bias.update(bias)
    profile.barrier_rate = overrides.pop("barrier_rate", 1.0)
    profile.avg_turns = overrides.pop("avg_turns", 5.0)  # very short -> aggressive
    return profile


def test_thief_weight_updates_stay_within_hard_bounds():
    extreme_profile = _saturated_profile()
    baseline = ThiefWeights()
    candidate = adaptation.derive_thief_weights(baseline, extreme_profile, None)

    bc_lo, bc_hi = adaptation.THIEF_BOUNDS["barrier_confinement"]
    td_lo, td_hi = adaptation.THIEF_BOUNDS["threat_distance"]
    assert bc_lo <= candidate.barrier_confinement <= bc_hi
    assert td_lo <= candidate.threat_distance <= td_hi


def test_cop_barrier_confidence_stays_within_hard_bounds():
    extreme_profile = _saturated_profile()
    candidate = adaptation.derive_cop_barrier_confidence(0.15, extreme_profile, None)
    lo, hi = adaptation.COP_BARRIER_CONFIDENCE_BOUNDS
    assert lo <= candidate <= hi


def test_low_confidence_profile_stays_close_to_baseline():
    """A single-game, low-confidence profile must only nudge the baseline a
    little, even if that one game looked extreme."""
    baseline = ThiefWeights()
    barely_seen = LearningProfile(sample_count=1, games_seen=1)
    barely_seen.barrier_rate = 1.0
    barely_seen.avg_turns = 1.0

    candidate = adaptation.derive_thief_weights(baseline, barely_seen, None)
    assert abs(candidate.barrier_confinement - baseline.barrier_confinement) < 0.2
    assert abs(candidate.threat_distance - baseline.threat_distance) < 0.4


def test_unknown_opponent_zero_confidence_returns_baseline_unchanged():
    baseline = ThiefWeights()
    empty_global = LearningProfile()  # never updated -- sample_count 0
    candidate = adaptation.derive_thief_weights(baseline, empty_global, None)
    assert candidate == baseline


def test_deterministic_behaviour_for_a_fixed_seed():
    """Same weights, same seed -> the exact same sequence of tie-break
    choices, so a match with a supplied seed reproduces exactly."""
    weights = adaptation.derive_thief_weights(ThiefWeights(), _saturated_profile(), None)
    a = RiskThiefStrategy(weights=weights, seed=42)
    b = RiskThiefStrategy(weights=weights, seed=42)
    assert a._rng.random() == b._rng.random()
