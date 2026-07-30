"""A deterministic sequential adjudicator, for tests only.

This is **not** the distributed turn model. The real one is simultaneous under
commit-reveal (DECISIONS.md D-6) and arrives in Phase 5. Here, the harness
applies the cop's action then the thief's, within one full turn, and adjudicates
the result -- which is enough to exercise the domain and nothing more.

The harness is the only object in the project that holds both positions. It does
so in its own fields, never inside a ``LocalState``; the two peer states remain
independent objects that could each have been produced on a different machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.capture import (
    evaluate_barrier_capture,
    evaluate_full_turn_capture,
)
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role
from police_thief.domain.events import DomainEvent, SubGameFinished
from police_thief.domain.exceptions import BlockedCellError
from police_thief.domain.scoring import ScoreResult, calculate_score
from police_thief.domain.simultaneity import (
    DEFAULT_SIMULTANEITY_POLICY,
    SimultaneityPolicy,
    TurnMovement,
)
from police_thief.domain.state import LocalState
from police_thief.domain.terminal import (
    TerminalResult,
    capture as terminal_capture,
    evaluate_move_ceiling,
    evaluate_survival,
)
from police_thief.domain.transition import apply_action, observe_barrier

Policy = Callable[[LocalState, SharedConfig], Action]


@dataclass(frozen=True, slots=True)
class TurnRecord:
    """What happened in one full turn."""

    turn: int
    cop_action: Action
    thief_action: Action
    cop_position: Coordinate
    thief_position: Coordinate
    events: tuple[DomainEvent, ...]
    terminal: TerminalResult | None


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """The result of a completed sub-game."""

    terminal: TerminalResult
    score: ScoreResult
    turns: int
    history: tuple[TurnRecord, ...]
    cop_state: LocalState
    thief_state: LocalState

    def summary(self) -> str:
        winner = self.terminal.winner.value if self.terminal.winner else "nobody"
        detail = (
            f" ({self.terminal.capture_reason.value})"
            if self.terminal.capture_reason
            else ""
        )
        return (
            f"{self.terminal.reason.value}{detail} on turn {self.terminal.turn}; "
            f"winner {winner}; cop {self.score.cop}, thief {self.score.thief}"
        )


@dataclass
class MatchHarness:
    """Drives one sub-game between two isolated local states.

    Mutable, unlike everything in the domain -- it is a test driver, and the
    states it holds are replaced wholesale on each step rather than edited.
    """

    config: SharedConfig
    cop: LocalState = field(init=False)
    thief: LocalState = field(init=False)
    policy: SimultaneityPolicy = DEFAULT_SIMULTANEITY_POLICY
    history: list[TurnRecord] = field(default_factory=list)
    simultaneity_collisions: int = 0
    """Times BLOCKED_MOVE_BECOMES_STAY was applied -- an unresolved rule."""

    def __post_init__(self) -> None:
        self.cop = LocalState.initial(Role.POLICE, self.config)
        self.thief = LocalState.initial(Role.THIEF, self.config)

    # ------------------------------------------------------------------
    # Omniscient view -- harness only
    # ------------------------------------------------------------------

    @property
    def cop_cell(self) -> Coordinate:
        """Test-only. Never reachable from a peer's own state."""
        return self.cop.position

    @property
    def thief_cell(self) -> Coordinate:
        """Test-only. Never reachable from a peer's own state."""
        return self.thief.position

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    def play_turn(
        self, cop_action: Action, thief_action: Action
    ) -> TurnRecord:
        """Apply one full turn and adjudicate it."""
        if self.is_finished:
            from police_thief.domain.exceptions import GameAlreadyFinishedError

            raise GameAlreadyFinishedError(
                "the sub-game has already ended; no further turn is possible"
            )

        cop_before = self.cop.position
        thief_before = self.thief.position
        events: list[DomainEvent] = []

        # --- cop acts -------------------------------------------------
        cop_result = apply_action(self.cop, cop_action, self.config)
        events.extend(cop_result.events)
        self.cop = cop_result.state

        # A declared barrier is public: the thief records it too (E-15).
        if cop_result.barrier_cell is not None:
            self.thief = observe_barrier(self.thief, cop_result.barrier_cell)

            # E-46: a barrier on the thief's cell captures at that moment,
            # before the thief acts.
            verdict = evaluate_barrier_capture(
                cop_result.barrier_cell, self.thief.position
            )
            if verdict:
                return self._finish(
                    terminal_capture(self.turn_number + 1, verdict.reason),
                    cop_action,
                    thief_action,
                    tuple(events),
                )

        # --- thief acts -----------------------------------------------
        # If the cop's barrier landed on the cell the thief had already chosen,
        # its move is no longer possible although nothing illegal was done. The
        # harness resolves that by standing still -- see
        # BLOCKED_MOVE_BECOMES_STAY: an unresolved rule, applied here only so a
        # demonstration can terminate, and never a ruling.
        try:
            thief_result = apply_action(self.thief, thief_action, self.config)
        except BlockedCellError:
            thief_action = Move(Direction.STAY)
            self.simultaneity_collisions += 1
            thief_result = apply_action(self.thief, thief_action, self.config)
        events.extend(thief_result.events)
        self.thief = thief_result.state

        turn = self.turn_number + 1
        self.cop = self.cop.advanced()
        self.thief = self.thief.advanced()

        # --- adjudicate ------------------------------------------------
        movement = TurnMovement(
            cop_before=cop_before,
            cop_after=self.cop.position,
            thief_before=thief_before,
            thief_after=self.thief.position,
        )
        verdict = evaluate_full_turn_capture(
            movement, self.thief, self.config, self.policy
        )
        if verdict:
            return self._finish(
                terminal_capture(turn, verdict.reason),
                cop_action,
                thief_action,
                tuple(events),
            )

        # Capture takes precedence over survival on the same turn (D-7).
        terminal = evaluate_survival(turn, self.config) or evaluate_move_ceiling(
            turn, self.config
        )
        if terminal:
            return self._finish(terminal, cop_action, thief_action, tuple(events))

        record = TurnRecord(
            turn=turn,
            cop_action=cop_action,
            thief_action=thief_action,
            cop_position=self.cop.position,
            thief_position=self.thief.position,
            events=tuple(events),
            terminal=None,
        )
        self.history.append(record)
        return record

    def _finish(
        self,
        terminal: TerminalResult,
        cop_action: Action,
        thief_action: Action,
        events: tuple[DomainEvent, ...],
    ) -> TurnRecord:
        self.cop = self.cop.finished(terminal)
        self.thief = self.thief.finished(terminal)
        events = (
            *events,
            SubGameFinished(
                reason=terminal.reason.value,
                winner=terminal.winner,
                turn=terminal.turn,
            ),
        )
        record = TurnRecord(
            turn=terminal.turn,
            cop_action=cop_action,
            thief_action=thief_action,
            cop_position=self.cop.position,
            thief_position=self.thief.position,
            events=events,
            terminal=terminal,
        )
        self.history.append(record)
        return record

    # ------------------------------------------------------------------
    # Driving
    # ------------------------------------------------------------------

    @property
    def turn_number(self) -> int:
        return self.cop.turn

    @property
    def is_finished(self) -> bool:
        return self.cop.is_finished

    def run(self, cop_policy: Policy, thief_policy: Policy) -> MatchOutcome:
        """Play to completion.

        Bounded by ``max_moves`` twice over: the terminal evaluation ends the
        sub-game, and the loop itself cannot exceed the ceiling. A test driver
        that can hang is a test driver that will.
        """
        ceiling = self.config.movement_and_barriers.max_moves
        while not self.is_finished and self.turn_number < ceiling:
            self.play_turn(
                cop_policy(self.cop, self.config),
                thief_policy(self.thief, self.config),
            )

        terminal = self.cop.terminal
        if terminal is None:  # pragma: no cover - defensive
            from police_thief.domain.terminal import max_moves_reached

            terminal = max_moves_reached(self.turn_number)
            self.cop = self.cop.finished(terminal)
            self.thief = self.thief.finished(terminal)

        return MatchOutcome(
            terminal=terminal,
            score=calculate_score(terminal, self.config),
            turns=terminal.turn,
            history=tuple(self.history),
            cop_state=self.cop,
            thief_state=self.thief,
        )
