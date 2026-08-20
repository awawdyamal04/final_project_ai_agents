#!/usr/bin/env python
"""Guarded promotion CLI (adaptive-learning sprint, Phase 6/10).

Evaluates whether the *global* learned profile's adjustment to the
production strategy is worth adopting as a new default, using the existing
offline benchmark harness across multiple seeds and, where available, more
than one opponent matchup. Deliberately never run automatically after a
real match (see ``peer/run.py``'s "candidate promotion: not evaluated") --
this is a separate, occasional, offline step a team runs on purpose.

    python scripts/learning_promote.py --role thief --games-per-seed 40
    python scripts/learning_promote.py --role police --games-per-seed 40

Never overwrites the shipped strategy defaults itself -- it only writes a
record under ``results/learning/promotions/`` stating promoted/rejected and
why. The production baseline is unaffected either way.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from police_thief.config.loader import load_shared_config  # noqa: E402
from police_thief.domain.enums import Role  # noqa: E402
from police_thief.learning import adaptation  # noqa: E402
from police_thief.learning.promotion import evaluate_candidate, save_promotion_record  # noqa: E402
from police_thief.learning.store import (  # noqa: E402
    DEFAULT_LEARNING_DIR,
    load_global_profile,
)
from police_thief.strategy.heuristics import CopStrategy, ThiefStrategy  # noqa: E402
from police_thief.strategy.thief_risk import RiskThiefStrategy  # noqa: E402
from police_thief.strategy.weights import ThiefWeights  # noqa: E402


def _thief_opponents() -> dict:
    return {"vs_baseline_cop": lambda seed, i: CopStrategy()}


def _cop_opponents() -> dict:
    return {
        "vs_baseline_thief": lambda seed, i: ThiefStrategy(),
        "vs_risk_thief": lambda seed, i: RiskThiefStrategy(seed=seed * 1000 + i + 500_000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["police", "thief"], required=True)
    parser.add_argument("--learning-dir", default=str(DEFAULT_LEARNING_DIR))
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--games-per-seed", type=int, default=40)
    args = parser.parse_args()

    role = Role.POLICE if args.role == "police" else Role.THIEF
    learning_dir = Path(args.learning_dir)
    config = load_shared_config("config/game.json")
    global_profile = load_global_profile(learning_dir)

    if role is Role.THIEF:
        candidate_weights = adaptation.derive_thief_weights(ThiefWeights(), global_profile, None)
        baseline_factory = lambda seed, i: RiskThiefStrategy(seed=seed * 1000 + i)  # noqa: E731
        candidate_factory = lambda seed, i: RiskThiefStrategy(  # noqa: E731
            weights=candidate_weights, seed=seed * 1000 + i
        )
        opponents = _thief_opponents()
        candidate_params = candidate_weights.to_dict()
    else:
        candidate_bc = adaptation.derive_cop_barrier_confidence(
            CopStrategy().barrier_confidence, global_profile, None
        )
        baseline_factory = lambda seed, i: CopStrategy()  # noqa: E731
        candidate_factory = lambda seed, i: CopStrategy(barrier_confidence=candidate_bc)  # noqa: E731
        opponents = _cop_opponents()
        candidate_params = {"barrier_confidence": candidate_bc}

    result = evaluate_candidate(
        role=role, config=config,
        baseline_factory=baseline_factory, candidate_factory=candidate_factory,
        opponent_factories=opponents, seeds=args.seeds, games_per_seed=args.games_per_seed,
    )
    path = save_promotion_record(role, candidate_params, result, learning_dir)

    print(f"role               {role.value}")
    print(f"baseline rates     {result.baseline_rates}")
    print(f"candidate rates    {result.candidate_rates}")
    print(f"mean improvement   {result.improvement_pp:.2f}pp")
    print(f"worst regression   {result.max_regression_pp:.2f}pp")
    print(f"verdict            {'PROMOTED' if result.promoted else 'REJECTED'}")
    print(f"reason             {result.reason}")
    print(f"saved              {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
