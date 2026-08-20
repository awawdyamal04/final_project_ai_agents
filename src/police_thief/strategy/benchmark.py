"""Local competitive benchmark harness (strategy sprint).

    python -m police_thief.strategy.benchmark --games 2000

Plays four matchups -- baseline-vs-baseline, new-cop-vs-baseline-thief,
baseline-cop-vs-new-thief, new-vs-new -- over multiple seeds, and writes a
machine-readable summary under ``results/strategy/``. Strategy + benchmarking
only: this drives the same offline
:class:`~police_thief.sim.harness.MatchHarness` the domain test suite already
uses, and touches no protocol, commit-reveal, capture-claim, audit, replay,
scoring or networking code.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.strategy.benchmark_match import play_benchmark_match
from police_thief.strategy.benchmark_metrics import MatchupSummary
from police_thief.strategy.cop_belief import BeliefCopStrategy
from police_thief.strategy.heuristics import CopStrategy, ThiefStrategy
from police_thief.strategy.thief_risk import RiskThiefStrategy
from police_thief.strategy.weights import CopWeights, ThiefWeights

RESULTS_DIR = Path("results/strategy")


def _matchups(
    cop_seed: int,
    thief_seed: int,
    cop_weights: CopWeights,
    thief_weights: ThiefWeights,
) -> dict:
    return {
        "baseline_cop_vs_baseline_thief": (CopStrategy(), ThiefStrategy()),
        "new_cop_vs_baseline_thief": (
            BeliefCopStrategy(weights=cop_weights, seed=cop_seed),
            ThiefStrategy(),
        ),
        "baseline_cop_vs_new_thief": (
            CopStrategy(),
            RiskThiefStrategy(weights=thief_weights, seed=thief_seed),
        ),
        "new_cop_vs_new_thief": (
            BeliefCopStrategy(weights=cop_weights, seed=cop_seed),
            RiskThiefStrategy(weights=thief_weights, seed=thief_seed),
        ),
    }


def run_benchmark(
    games: int,
    seeds: list[int],
    cop_weights: CopWeights | None = None,
    thief_weights: ThiefWeights | None = None,
) -> dict:
    config = load_shared_config("config/game.json")
    cop_weights = cop_weights or CopWeights()
    thief_weights = thief_weights or ThiefWeights()
    labels = list(_matchups(0, 0, cop_weights, thief_weights).keys())
    summaries = {label: MatchupSummary(label) for label in labels}

    per_seed_games = max(1, games // len(seeds))
    for seed in seeds:
        for game_index in range(per_seed_games):
            cop_seed = seed * 100_000 + game_index
            thief_seed = seed * 100_000 + game_index + 50_000
            matchups = _matchups(cop_seed, thief_seed, cop_weights, thief_weights)
            for label, (cop, thief) in matchups.items():
                stats = play_benchmark_match(config, cop, thief)
                summaries[label].add(stats)

    return {label: summary.to_dict() for label, summary in summaries.items()}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=2000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument(
        "--weights",
        default=None,
        help="path to a results/strategy/selected_weights.json from the sweep",
    )
    return parser


def _load_weights(path: str | None) -> tuple[CopWeights, ThiefWeights]:
    if not path:
        return CopWeights(), ThiefWeights()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return (
        CopWeights.from_dict(data["cop"]["weights"]),
        ThiefWeights.from_dict(data["thief"]["weights"]),
    )


def main() -> int:
    args = _build_parser().parse_args()
    cop_weights, thief_weights = _load_weights(args.weights)
    results = run_benchmark(args.games, args.seeds, cop_weights, thief_weights)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat().replace(":", "-")
    out_path = RESULTS_DIR / f"benchmark_{ts}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    for label, summary in results.items():
        print(
            f"{label:32s} police={summary['police_win_rate']:.2%} "
            f"thief={summary['thief_win_rate']:.2%} "
            f"avg_turn={summary['avg_terminal_turn']:.1f} "
            f"games={summary['games']}"
        )
    print(f"saved {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
