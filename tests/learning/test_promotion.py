"""Guarded promotion: accepts a genuine improvement, rejects a regression.

``play_benchmark_match`` is monkeypatched with a deterministic fake so the
verdict depends only on the promotion arithmetic being tested, not on real
gameplay variance -- real-gameplay coverage lives in
``strategy/test_benchmark_match.py`` and the strategy sprint's own tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import police_thief.learning.promotion as promotion
from police_thief.domain.enums import Role


class _Baseline:
    name = "baseline"


class _Candidate:
    name = "candidate"


@dataclass
class _FakeOutcome:
    winner: Role | None


def _fake_stats(winner: Role | None) -> SimpleNamespace:
    return SimpleNamespace(outcome=SimpleNamespace(terminal=_FakeOutcome(winner)))


def _install_fake_bench(
    monkeypatch, *, candidate_win_rate: float, baseline_win_rate: float, role: Role
):
    """Deterministic: candidate wins ``candidate_win_rate`` fraction of its
    games, baseline wins ``baseline_win_rate`` of its own -- by index parity,
    not RNG, so this is exactly reproducible."""

    def fake_play(config, cop, thief):
        actor = cop if role is Role.POLICE else thief
        rate = candidate_win_rate if isinstance(actor, _Candidate) else baseline_win_rate
        fake_play.counter += 1
        wins_needed = round(rate * 10)
        won = (fake_play.counter % 10) < wins_needed
        return _fake_stats(role if won else None)

    fake_play.counter = -1
    monkeypatch.setattr(promotion, "play_benchmark_match", fake_play)


def test_promotion_accepts_a_genuinely_better_candidate(monkeypatch):
    _install_fake_bench(
        monkeypatch, candidate_win_rate=0.9, baseline_win_rate=0.5, role=Role.THIEF
    )
    result = promotion.evaluate_candidate(
        role=Role.THIEF,
        config=None,
        baseline_factory=lambda seed, i: _Baseline(),
        candidate_factory=lambda seed, i: _Candidate(),
        opponent_factories={"vs_x": lambda seed, i: object()},
        seeds=[1, 2],
        games_per_seed=10,
    )
    assert result.promoted is True
    assert result.improvement_pp >= promotion.IMPROVEMENT_THRESHOLD_PP


def test_promotion_rejects_a_regression(monkeypatch):
    _install_fake_bench(
        monkeypatch, candidate_win_rate=0.3, baseline_win_rate=0.5, role=Role.THIEF
    )
    result = promotion.evaluate_candidate(
        role=Role.THIEF,
        config=None,
        baseline_factory=lambda seed, i: _Baseline(),
        candidate_factory=lambda seed, i: _Candidate(),
        opponent_factories={"vs_x": lambda seed, i: object()},
        seeds=[1, 2],
        games_per_seed=10,
    )
    assert result.promoted is False
    assert result.max_regression_pp > promotion.REGRESSION_LIMIT_PP


def test_promotion_rejects_a_marginal_non_meaningful_improvement(monkeypatch):
    _install_fake_bench(
        monkeypatch, candidate_win_rate=0.51, baseline_win_rate=0.5, role=Role.THIEF
    )
    result = promotion.evaluate_candidate(
        role=Role.THIEF,
        config=None,
        baseline_factory=lambda seed, i: _Baseline(),
        candidate_factory=lambda seed, i: _Candidate(),
        opponent_factories={"vs_x": lambda seed, i: object()},
        seeds=[1],
        games_per_seed=10,
    )
    assert result.promoted is False
