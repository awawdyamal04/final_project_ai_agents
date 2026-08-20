#!/usr/bin/env python
"""CLI for the strategy weight search (competitive strategy sprint).

    python scripts/strategy_sweep.py --trials 40 --games-per-seed 12

Search logic lives in ``police_thief.strategy.sweep`` so it stays importable
and testable; this script only parses arguments and writes the result.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from police_thief.strategy.sweep import sweep  # noqa: E402

RESULTS = Path("results/strategy")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=40)
    parser.add_argument("--games-per-seed", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    train_seeds, eval_seeds = [11, 12, 13], [21, 22, 23]

    best_cop, cop_score, best_thief, thief_score = sweep(
        args.trials, train_seeds, eval_seeds, args.games_per_seed, rng
    )

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "selected_weights.json"
    out.write_text(
        json.dumps(
            {
                "cop": {
                    "weights": best_cop.to_dict(),
                    "eval_police_win_rate_vs_new_thief": cop_score,
                },
                "thief": {
                    "weights": best_thief.to_dict(),
                    "eval_thief_win_rate_vs_baseline_cop": thief_score,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"cop:   eval police win rate vs new thief   = {cop_score:.2%}")
    print(f"thief: eval thief win rate vs baseline cop = {thief_score:.2%}")
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
