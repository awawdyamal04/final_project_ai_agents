"""Run N automated in-process games with the real strategies.

    python scripts/run_games.py --games 20

Uses the existing test-only :class:`MatchHarness` for adjudication -- the same
boundary Phase 1 established, and the same unresolved-simultaneity policy, which
stays behind ``SimultaneityPolicy`` and is **not** settled here.

Each peer runs its own tracker and strategy and sees only its own
:class:`LocalView`. The harness holds both positions to adjudicate captures, as
it always has; the strategies cannot reach it.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from police_thief.config.loader import build_shared_config, load_shared_config
from police_thief.domain.actions import PlaceBarrier
from police_thief.domain.board import Board
from police_thief.domain.enums import Role
from police_thief.sim.harness import MatchHarness
from police_thief.strategy.heuristics import strategy_for
from police_thief.strategy.tracker import OpponentTracker

REPO_ROOT = Path(__file__).resolve().parents[1]


def play_one(config, thief_start=None, cop_start=None):
    """Play one sub-game with both sides driven by their real strategies."""
    if thief_start or cop_start:
        raw = json.loads(json.dumps(config.raw))
        if thief_start:
            raw["board_and_agents"]["thief_start"] = list(thief_start)
        if cop_start:
            raw["board_and_agents"]["cop_start"] = list(cop_start)
        config = build_shared_config(raw)

    harness = MatchHarness(config)
    board = Board.from_config(config)
    trackers = {
        Role.POLICE: OpponentTracker(Role.POLICE, config, board),
        Role.THIEF: OpponentTracker(Role.THIEF, config, board),
    }
    strategies = {r: strategy_for(r.value) for r in Role}

    while not harness.is_finished:
        chosen = {}
        for role, state in ((Role.POLICE, harness.cop), (Role.THIEF, harness.thief)):
            tracker = trackers[role]
            tracker.note_own_position(state.position)
            chosen[role] = strategies[role].choose(tracker.view(state))

        record = harness.play_turn(chosen[Role.POLICE], chosen[Role.THIEF])

        # Each peer folds in what the other did -- belief and scent only.
        for role in (Role.POLICE, Role.THIEF):
            other = Role.THIEF if role is Role.POLICE else Role.POLICE
            own = harness.cop if role is Role.POLICE else harness.thief
            if isinstance(chosen[role], PlaceBarrier):
                trackers[role].observe_barrier(chosen[role].cell)
            trackers[role].observe_opponent_action(
                chosen[other], own_cell=own.position
            )
        if record.terminal is not None:
            break

    return harness


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--shared", default="config/game.json")
    args = parser.parse_args()

    config = load_shared_config(REPO_ROOT / args.shared)

    # Vary the agreed start layout across games -- both cells are NEGOTIABLE, so
    # this stays inside the rules while exercising more than one geometry.
    layouts = [
        (None, None),
        ((3, 3), (6, 6)), ((2, 2), (0, 6)), ((4, 4), (0, 0)),
        ((1, 5), (5, 1)), ((5, 2), (1, 4)), ((2, 5), (6, 0)),
        ((3, 1), (3, 6)), ((6, 3), (0, 3)), ((4, 2), (1, 6)),
    ]

    outcomes, winners, turns, barriers = Counter(), Counter(), [], []
    for game in range(args.games):
        thief_start, cop_start = layouts[game % len(layouts)]
        harness = play_one(config, thief_start, cop_start)
        terminal = harness.cop.terminal
        assert terminal is not None, "game did not terminate"

        outcomes[terminal.reason.value] += 1
        winners[terminal.winner.value if terminal.winner else "none"] += 1
        turns.append(terminal.turn)
        barriers.append(harness.cop.barriers_placed)

        detail = (
            f" ({terminal.capture_reason.value})" if terminal.capture_reason else ""
        )
        print(
            f"  game {game + 1:>2}  {terminal.reason.value}{detail:<28} "
            f"turn {terminal.turn:>3}  barriers {harness.cop.barriers_placed}"
        )

    print()
    print(f"  games            {args.games}")
    print(f"  outcomes         {dict(outcomes)}")
    print(f"  winners          {dict(winners)}")
    print(f"  turns  min/avg/max  {min(turns)} / {sum(turns)/len(turns):.1f} / {max(turns)}")
    print(f"  barriers used    avg {sum(barriers)/len(barriers):.1f}")
    print(f"  all terminated   {len(turns) == args.games}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
