"""Play one benchmark sub-game between two strategies (competitive strategy
sprint -- benchmark harness).

Drives the existing offline :class:`~police_thief.sim.harness.MatchHarness`
(already used by the domain test suite) and updates each side's belief/scent
tracker exactly like a live peer does in
:meth:`~police_thief.peer.orchestrator.PeerOrchestrator.play_turn` -- without
touching the network, commit-reveal, capture-claim, audit or replay layers
at all, and without adding a second copy of the harness's own adjudication
logic.

No hint/verbal layer: composing a hint normally goes through the (possibly
LLM-backed) verbal provider, which is far too slow for thousands of local
games and orthogonal to movement/barrier strategy quality. Both sides
therefore see empty hints here -- a documented scope simplification, not a
silent one.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import PlaceBarrier
from police_thief.domain.enums import Role
from police_thief.domain.scoring import calculate_score
from police_thief.domain.terminal import max_moves_reached
from police_thief.sim.harness import MatchHarness, MatchOutcome
from police_thief.strategy.base import BaseStrategy
from police_thief.strategy.tracker import OpponentTracker


@dataclass(frozen=True)
class MatchStats:
    """One benchmark game's result plus the light extra telemetry the
    competitive sprint's metric list asks for."""

    outcome: MatchOutcome
    invalid_actions: int
    avg_cop_mobility: float
    avg_thief_mobility: float


def play_benchmark_match(
    config: SharedConfig, cop_strategy: BaseStrategy, thief_strategy: BaseStrategy
) -> MatchStats:
    harness = MatchHarness(config)
    cop_tracker = OpponentTracker(Role.POLICE, config, harness.cop.board)
    thief_tracker = OpponentTracker(Role.THIEF, config, harness.thief.board)

    invalid_actions = 0
    mobility_cop = 0.0
    mobility_thief = 0.0
    ceiling = config.movement_and_barriers.max_moves

    while not harness.is_finished and harness.turn_number < ceiling:
        cop_tracker.note_own_position(harness.cop.position)
        thief_tracker.note_own_position(harness.thief.position)
        mobility_cop += len(harness.cop.board.passable_neighbours(harness.cop.position))
        mobility_thief += len(
            harness.thief.board.passable_neighbours(harness.thief.position)
        )

        cop_action = cop_strategy.choose(cop_tracker.view(harness.cop))
        thief_action = thief_strategy.choose(thief_tracker.view(harness.thief))
        record = harness.play_turn(cop_action, thief_action)
        if record.thief_action != thief_action:
            invalid_actions += 1  # the simultaneity collision fallback fired

        if isinstance(record.cop_action, PlaceBarrier):
            cop_tracker.observe_barrier(record.cop_action.cell)
        cop_tracker.observe_opponent_action(
            record.thief_action, own_cell=harness.cop.position
        )
        thief_tracker.observe_opponent_action(
            record.cop_action, own_cell=harness.thief.position
        )

    terminal = harness.cop.terminal
    if terminal is None:  # pragma: no cover - defensive, mirrors MatchHarness.run
        terminal = max_moves_reached(harness.turn_number)
        harness.cop = harness.cop.finished(terminal)
        harness.thief = harness.thief.finished(terminal)

    outcome = MatchOutcome(
        terminal=terminal,
        score=calculate_score(terminal, config),
        turns=terminal.turn,
        history=tuple(harness.history),
        cop_state=harness.cop,
        thief_state=harness.thief,
    )
    turns = max(1, outcome.turns)
    return MatchStats(
        outcome=outcome,
        invalid_actions=invalid_actions,
        avg_cop_mobility=mobility_cop / turns,
        avg_thief_mobility=mobility_thief / turns,
    )
