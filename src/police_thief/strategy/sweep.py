"""Random search over :class:`CopWeights`/:class:`ThiefWeights` (competitive
strategy sprint). Library half of ``scripts/strategy_sweep.py`` -- the CLI
stays a thin wrapper so this stays importable and testable on its own.

Two independent searches, each against a *fixed* opponent so neither chases a
moving target: cop weights are scored against ``RiskThiefStrategy`` (the
harder, tuned thief -- the baseline thief is already beaten 100% of the time
by the shipped defaults, leaving no headroom to measure improvement there,
see ``results/strategy/notes.md``); thief weights are scored against the
baseline ``CopStrategy``.

Train seeds pick a configuration; a disjoint set of evaluation seeds scores
it, so a configuration that only got lucky on the seeds it was chosen on
cannot be reported as the winner.
"""

from __future__ import annotations

import random
from dataclasses import replace

from police_thief.config.loader import load_shared_config
from police_thief.domain.enums import Role
from police_thief.strategy.benchmark_match import play_benchmark_match
from police_thief.strategy.cop_belief import BeliefCopStrategy
from police_thief.strategy.heuristics import CopStrategy
from police_thief.strategy.thief_risk import RiskThiefStrategy
from police_thief.strategy.weights import CopWeights, ThiefWeights

COP_RANGES = {
    "capture_now": (6.0, 18.0),
    "capture_soon": (2.0, 12.0),
    "belief": (3.0, 14.0),
    "scent": (1.0, 6.0),
    "edge_push": (0.0, 4.0),
    "info_gain": (0.0, 3.0),
    "opponent_bias": (0.0, 0.6),
    "near_tie_epsilon": (0.0, 0.15),
}
THIEF_RANGES = {
    "threat_distance": (0.5, 4.0),
    "mobility": (0.5, 3.0),
    "future_mobility": (0.0, 1.5),
    "corner_penalty": (0.0, 6.0),
    "barrier_confinement": (0.0, 3.0),
    "scent": (1.0, 8.0),
    "opponent_bias": (0.0, 3.0),
}


def _sample(base, ranges: dict, rng: random.Random):
    overrides = {k: round(rng.uniform(*bounds), 3) for k, bounds in ranges.items()}
    return replace(base, **overrides)


def _win_rate(config, cop, thief, seeds, games_per_seed, want: Role) -> float:
    wins, total = 0, 0
    for seed in seeds:
        for i in range(games_per_seed):
            stats = play_benchmark_match(config, cop(seed, i), thief(seed, i))
            total += 1
            if stats.outcome.terminal.winner is want:
                wins += 1
    return wins / max(1, total)


def _cop_factory(weights):
    return lambda seed, i: BeliefCopStrategy(weights=weights, seed=seed * 1000 + i)


def _thief_factory(weights):
    return lambda seed, i: RiskThiefStrategy(
        weights=weights, seed=seed * 1000 + i + 500_000
    )


def sweep(trials: int, train_seeds, eval_seeds, games_per_seed: int, rng: random.Random):
    config = load_shared_config("config/game.json")
    fixed_thief = _thief_factory(ThiefWeights())
    fixed_cop = lambda seed, i: CopStrategy()  # noqa: E731

    best_cop, best_thief = CopWeights(), ThiefWeights()
    best_cop_score = _win_rate(
        config, _cop_factory(best_cop), fixed_thief, eval_seeds, games_per_seed, Role.POLICE
    )
    best_thief_score = _win_rate(
        config, fixed_cop, _thief_factory(best_thief), eval_seeds, games_per_seed, Role.THIEF
    )

    for _ in range(trials):
        cw = _sample(CopWeights(), COP_RANGES, rng)
        cf = _cop_factory(cw)
        train = _win_rate(config, cf, fixed_thief, train_seeds, games_per_seed, Role.POLICE)
        if train >= best_cop_score:
            score = _win_rate(config, cf, fixed_thief, eval_seeds, games_per_seed, Role.POLICE)
            if score > best_cop_score:
                best_cop, best_cop_score = cw, score

        tw = _sample(ThiefWeights(), THIEF_RANGES, rng)
        tf = _thief_factory(tw)
        train_t = _win_rate(config, fixed_cop, tf, train_seeds, games_per_seed, Role.THIEF)
        if train_t >= best_thief_score:
            score_t = _win_rate(config, fixed_cop, tf, eval_seeds, games_per_seed, Role.THIEF)
            if score_t > best_thief_score:
                best_thief, best_thief_score = tw, score_t

    return best_cop, best_cop_score, best_thief, best_thief_score
