"""Headless single-process simulation.

    python -m police_thief.sim.headless --shared config/game.json

Runs one sub-game between two isolated local states with trivial deterministic
policies, and prints a concise summary. Test infrastructure, not the game: the
real system runs two peers in two separate processes over FastMCP, with no
component that sees both sides.
"""

from __future__ import annotations

import argparse
import sys

from police_thief.config.exceptions import ConfigError
from police_thief.config.loader import load_shared_config
from police_thief.sim.harness import MatchHarness
from police_thief.sim.policies import cycle_directions, first_legal_move


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m police_thief.sim.headless",
        description=(
            "Run one headless sub-game with trivial deterministic policies. "
            "Test infrastructure -- not the distributed turn model."
        ),
    )
    parser.add_argument("--shared", default="config/game.json")
    parser.add_argument(
        "--show-turns",
        type=int,
        default=0,
        metavar="N",
        help="print the first N turns",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        config = load_shared_config(args.shared)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    harness = MatchHarness(config)
    board = config.board_and_agents

    print("headless sub-game (single process, test harness)")
    print(f"  board                {config.grid_size}x{config.grid_size}")
    print(f"  cop start            {list(board.cop_start)}")
    print(f"  thief start          {list(board.thief_start)}")
    print(f"  survival threshold   {config.movement_and_barriers.survival_threshold}")
    print(f"  move ceiling         {config.movement_and_barriers.max_moves}")
    print(f"  barrier quota        {config.movement_and_barriers.max_barriers}")
    print(f"  simultaneity policy  {harness.policy.name} (not PDF-resolved)")

    outcome = harness.run(first_legal_move, cycle_directions)

    if args.show_turns:
        print("  turns:")
        for record in outcome.history[: args.show_turns]:
            print(
                f"    {record.turn:>3}  cop {record.cop_action}"
                f"   thief {record.thief_action}"
            )

    print(f"  result               {outcome.summary()}")
    print(f"  turns played         {outcome.turns}")
    print(f"  barriers placed      {outcome.cop_state.barriers_placed}")

    # The peers' own states never held the other's position; the harness did.
    print("  cop state keys       " + ", ".join(sorted(outcome.cop_state.to_public_dict())))
    print("  (no opponent position in either peer's state)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
