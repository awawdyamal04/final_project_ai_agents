"""Per-peer tracking of the opponent: belief map plus reconstructed scent.

Holds the two pieces of evidence a peer legally has about its opponent, and
nothing else.

Where the opponent's scent comes from
-------------------------------------
Scent is a function of a trajectory. With no central server, a peer cannot
observe the opponent's field directly -- so it *reconstructs* it from the
opponent's revealed actions, which the commit-reveal protocol already delivers
each turn. Nothing new crosses the wire and the protocol is untouched.

This reconstruction is exact only because the current reveal discloses the
opponent's action precisely. That has a consequence worth stating plainly: a
peer that dead-reckons from the agreed start cell can pin the opponent exactly,
which would make the belief map redundant. The machinery here is therefore built
to carry genuine uncertainty -- diffusion when a move is unknown, scent as a
likelihood, impossible-cell exclusion -- and simply happens to be well-informed
under the present reveal semantics. See OPEN_QUESTIONS.md Q-17, which is a
question for the opponent negotiation, not something to resolve unilaterally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import Action, Move, PlaceBarrier
from police_thief.domain.belief import BeliefMap
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role
from police_thief.domain.scent import ScentField
from police_thief.domain.state import LocalState
from police_thief.strategy.base import LocalView

RECENT_WINDOW = 8
"""How many of our own past cells to remember, for loop avoidance. Long enough
to break an oscillation, short enough that a legitimate return is still open."""


@dataclass
class OpponentTracker:
    """One peer's evidence about the other side."""

    role: Role
    config: SharedConfig
    board: Board
    belief: BeliefMap = field(init=False)
    opponent_scent: ScentField = field(init=False)
    recent_cells: list[Coordinate] = field(default_factory=list)
    hint_reliability: float = 0.5
    """How much this opponent's hints have been worth so far, 0..1.

    Starts at even odds and moves with the evidence. Scent cannot be forged, so
    it is the yardstick: a hint that agrees with the trail earns trust, one that
    contradicts it loses trust. A peer that lies consistently therefore ends up
    with hints that barely move our belief -- which is the cost of lying.
    """
    hints_seen: int = 0
    hints_contradicted: int = 0
    _believed_cell: Coordinate | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        opening = self.config.board_and_agents
        start = (
            opening.thief_start if self.role is Role.POLICE else opening.cop_start
        )
        # The opponent's start cell is an agreed, signed condition -- both peers
        # hold it. Seeding from it is reading the shared constitution, not
        # peeking at local truth.
        self._believed_cell = Coordinate.from_pair(start)
        self.belief = BeliefMap.certain(self.board, self._believed_cell)
        self.opponent_scent = ScentField.for_config(self.config, self.board)
        self.opponent_scent.emit(self._believed_cell)

    # ------------------------------------------------------------------

    def note_own_position(self, cell: Coordinate) -> None:
        self.recent_cells.append(cell)
        if len(self.recent_cells) > RECENT_WINDOW:
            self.recent_cells.pop(0)

    def observe_barrier(self, cell: Coordinate) -> None:
        """A declared barrier changes the board for both sides."""
        if not self.board.is_blocked(cell):
            self.board = self.board.with_barrier(cell)
            self.belief.board = self.board
            self.opponent_scent.board = self.board
        self.belief.exclude_impossible()

    def observe_opponent_action(
        self, action: Action, *, own_cell: Coordinate
    ) -> None:
        """Fold a revealed opponent action into belief and scent."""
        direction = action.direction if isinstance(action, Move) else None

        if isinstance(action, PlaceBarrier):
            # The cop forgoes movement to place, so its cell is unchanged.
            self.observe_barrier(action.cell)
            self.belief.predict(None if direction else None)
        else:
            self.belief.predict(direction)

        if self._believed_cell is not None and direction is not None:
            stepped = self._believed_cell.shifted(direction)
            if self.board.is_passable(stepped):
                self._believed_cell = stepped

        if self._believed_cell is not None:
            self.opponent_scent.advance_turn(self._believed_cell)
        else:
            self.opponent_scent.decay()

        self.belief.update_from_scent(self.opponent_scent)
        # Our own cell is one the opponent demonstrably is not on: if it were,
        # the turn would already have ended in a capture.
        self.belief.exclude_impossible(disproven={own_cell})

    # ------------------------------------------------------------------

    def note_hint(self, reading, own_cell: Coordinate) -> None:
        """Fold an incoming hint into the belief, weighted by earned trust.

        The claim is checked against the scent first. Chapter 4's worked example
        is exactly this: a thief announcing it went north while the whole trail
        sits in the south-east has given itself away, because the environment
        does not lie. So a contradicted hint both lowers trust *and* is not
        allowed to move the belief.
        """
        direction = getattr(reading, "claimed_direction", None)
        clarity = float(getattr(reading, "confidence", 0.0) or 0.0)
        if direction is None or clarity <= 0.0:
            return

        self.hints_seen += 1
        supported = self._scent_supports(direction)

        if supported:
            self.hint_reliability = min(1.0, self.hint_reliability + 0.1)
        else:
            self.hints_contradicted += 1
            self.hint_reliability = max(0.0, self.hint_reliability - 0.2)
            # Contradicted by evidence that cannot be faked: believe the trail.
            return

        weight = clarity * self.hint_reliability
        if weight <= 0.0:
            return

        shifted: dict[Coordinate, float] = {}
        for cell, mass in self.belief.probabilities.items():
            target = cell.shifted(direction)
            if self.board.is_passable(target):
                shifted[target] = shifted.get(target, 0.0) + mass * weight
            shifted[cell] = shifted.get(cell, 0.0) + mass * (1.0 - weight)

        self.belief.probabilities = shifted
        self.belief.exclude_impossible(disproven={own_cell})

    def _scent_supports(self, direction: Direction) -> bool:
        """Does the sensed trail point the way the hint claims?

        With no trail yet there is nothing to contradict, so a claim is taken at
        face value.
        """
        peak = self.opponent_scent.peak()
        if peak is None or self._believed_cell is None:
            return True
        scent_cell, _ = peak
        expected = self._believed_cell.shifted(direction)
        return expected.manhattan_distance_to(
            scent_cell
        ) <= self._believed_cell.manhattan_distance_to(scent_cell)

    def view(self, state: LocalState) -> LocalView:
        """Bundle the legal evidence for the strategy."""
        return LocalView(
            state=state,
            config=self.config,
            belief=self.belief,
            opponent_scent=self.opponent_scent,
            recent_cells=tuple(self.recent_cells),
        )
