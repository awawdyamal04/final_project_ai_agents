"""Guarded promotion gate for a learned candidate configuration.

A learned candidate never becomes production just because the last match was
lost. It must beat the current baseline across multiple deterministic seeds
and, where available, more than one opponent, using the existing offline
benchmark harness (``strategy/benchmark_match.py`` -- no protocol, network,
or replay code involved). Conservative rule (sprint brief, adapted to this
project's win-rate metrics):

* candidate must improve the mean win rate across matchups by >= 2
  percentage points, AND
* candidate must not regress *any single* matchup's win rate by more than 1
  percentage point,

otherwise the candidate is rejected and the baseline remains production.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.domain.enums import Role
from police_thief.strategy.benchmark_match import play_benchmark_match

IMPROVEMENT_THRESHOLD_PP = 2.0
REGRESSION_LIMIT_PP = 1.0
PROMOTIONS_SUBDIR = "promotions"


@dataclass(frozen=True)
class PromotionResult:
    promoted: bool
    reason: str
    baseline_rates: dict[str, float]
    candidate_rates: dict[str, float]
    improvement_pp: float
    max_regression_pp: float


def _win_rate(
    config: SharedConfig,
    role: Role,
    strategy_factory,
    opponent_factory,
    seeds: list[int],
    games_per_seed: int,
) -> float:
    wins, total = 0, 0
    for seed in seeds:
        for i in range(games_per_seed):
            cop = strategy_factory(seed, i) if role is Role.POLICE else opponent_factory(seed, i)
            thief = opponent_factory(seed, i) if role is Role.POLICE else strategy_factory(seed, i)
            stats = play_benchmark_match(config, cop, thief)
            total += 1
            if stats.outcome.terminal.winner is role:
                wins += 1
    return 100.0 * wins / max(1, total)


def evaluate_candidate(
    *,
    role: Role,
    config: SharedConfig,
    baseline_factory,
    candidate_factory,
    opponent_factories: dict[str, Any],
    seeds: list[int],
    games_per_seed: int,
) -> PromotionResult:
    """Run baseline and candidate through the same matchups/seeds and decide."""
    baseline_rates = {
        label: _win_rate(config, role, baseline_factory, opp, seeds, games_per_seed)
        for label, opp in opponent_factories.items()
    }
    candidate_rates = {
        label: _win_rate(config, role, candidate_factory, opp, seeds, games_per_seed)
        for label, opp in opponent_factories.items()
    }

    deltas = {label: candidate_rates[label] - baseline_rates[label] for label in baseline_rates}
    improvement = sum(deltas.values()) / max(1, len(deltas))
    max_regression = -min(deltas.values(), default=0.0)

    if improvement >= IMPROVEMENT_THRESHOLD_PP and max_regression <= REGRESSION_LIMIT_PP:
        promoted, reason = True, (
            f"mean improvement {improvement:.2f}pp >= {IMPROVEMENT_THRESHOLD_PP}pp "
            f"and worst regression {max_regression:.2f}pp <= {REGRESSION_LIMIT_PP}pp"
        )
    else:
        promoted, reason = False, (
            f"mean improvement {improvement:.2f}pp (need >= {IMPROVEMENT_THRESHOLD_PP}pp) "
            f"or worst regression {max_regression:.2f}pp (limit {REGRESSION_LIMIT_PP}pp)"
        )

    return PromotionResult(
        promoted=promoted,
        reason=reason,
        baseline_rates=baseline_rates,
        candidate_rates=candidate_rates,
        improvement_pp=improvement,
        max_regression_pp=max_regression,
    )


def save_promotion_record(
    role: Role,
    candidate_params: dict[str, Any],
    result: PromotionResult,
    learning_dir: Path,
) -> Path:
    """Persist the candidate, the benchmark result, and the verdict -- the
    production baseline itself is never touched by this, so it is always
    trivially recoverable regardless of what gets written here."""
    out_dir = Path(learning_dir) / PROMOTIONS_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat().replace(":", "-")
    path = out_dir / f"{role.value}_{ts}.json"
    payload = {
        "role": role.value,
        "timestamp": ts,
        "candidate_params": candidate_params,
        "baseline_rates": result.baseline_rates,
        "candidate_rates": result.candidate_rates,
        "improvement_pp": result.improvement_pp,
        "max_regression_pp": result.max_regression_pp,
        "promoted": result.promoted,
        "reason": result.reason,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
