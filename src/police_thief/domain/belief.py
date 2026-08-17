"""Belief map: a normalised distribution over the opponent's possible cell.

Each peer keeps one of these about the *other* side. It never contains the
opponent's true position -- it contains a probability for every legal cell, and
the peer's best guess is the argmax, which may well be wrong.

The update cycle is the standard predict/correct pair:

1. **Predict** -- spread the distribution through the motion model. Given a
   revealed action the spread is exact; without one it diffuses over every legal
   move including standing still.
2. **Correct** -- multiply by a likelihood derived from the observed scent, then
   zero out cells that are impossible (off board, barriered, or locally
   disproven), then renormalise.

Cells the peer can rule out on its own -- notably its own cell, when it knows it
is not sharing a square -- are excluded rather than left at low probability.

Everything here is deterministic: the same inputs give the same distribution, so
two peers replaying the same evidence agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ORTHOGONAL_DIRECTIONS, Direction
from police_thief.domain.scent import ScentField

_EPSILON = 1e-12


@dataclass
class BeliefMap:
    """A normalised probability distribution over board cells."""

    board: Board
    probabilities: dict[Coordinate, float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def uniform(cls, board: Board) -> BeliefMap:
        """Total ignorance: every passable cell equally likely."""
        cells = [c for c in board.all_cells() if not board.is_blocked(c)]
        weight = 1.0 / len(cells)
        return cls(board, dict.fromkeys(cells, weight))

    @classmethod
    def certain(cls, board: Board, cell: Coordinate) -> BeliefMap:
        """A point mass -- used when the opponent's start cell is agreed."""
        return cls(board, {cell: 1.0})

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def probability_at(self, cell: Coordinate) -> float:
        return self.probabilities.get(cell, 0.0)

    def total(self) -> float:
        return sum(self.probabilities.values())

    def is_normalised(self, tolerance: float = 1e-9) -> bool:
        return abs(self.total() - 1.0) <= tolerance

    def peak(self) -> Coordinate | None:
        """Most likely cell. Ties broken by coordinate order, for determinism."""
        if not self.probabilities:
            return None
        return max(
            self.probabilities,
            key=lambda c: (self.probabilities[c], -c.row, -c.col),
        )

    def entropy_cells(self) -> int:
        """How many cells still carry meaningful probability."""
        return sum(1 for p in self.probabilities.values() if p > 1e-6)

    # ------------------------------------------------------------------
    # Update cycle
    # ------------------------------------------------------------------

    def normalise(self, *, forbidden: set[Coordinate] | None = None) -> None:
        """Rescale to sum to 1, falling back to uniform if all mass is gone.

        The fallback matters: contradictory evidence can zero every cell, and a
        peer with an empty belief has no basis for any decision. Resetting to
        uniform says "I no longer know", which is the truthful state.

        ``forbidden`` cells stay excluded through that reset. Losing track of
        the opponent is not a reason to start believing it is somewhere we have
        just proved it is not.
        """
        total = self.total()
        if total <= _EPSILON:
            fresh = BeliefMap.uniform(self.board).probabilities
            for cell in forbidden or ():
                fresh.pop(cell, None)
            share = sum(fresh.values()) or 1.0
            self.probabilities = {c: v / share for c, v in fresh.items()}
            return
        self.probabilities = {
            cell: value / total
            for cell, value in self.probabilities.items()
            if value / total > _EPSILON
        }

    def exclude(self, cells: set[Coordinate]) -> None:
        """Zero out cells ruled out on local evidence, then renormalise."""
        for cell in cells:
            self.probabilities.pop(cell, None)
        self.normalise(forbidden=cells)

    def exclude_impossible(self, *, disproven: set[Coordinate] | None = None) -> None:
        """Remove off-board, barriered and locally disproven cells."""
        gone = {
            cell
            for cell in self.probabilities
            if not self.board.contains(cell) or self.board.is_blocked(cell)
        }
        if disproven:
            gone |= disproven
        self.exclude(gone)

    def predict(self, direction: Direction | None = None) -> None:
        """Propagate through the motion model.

        With ``direction``, every cell shifts by that step -- the opponent
        revealed what it did. Without one, mass spreads to each legal
        destination and to staying put, which is the honest prior when the move
        is unknown.
        """
        moved: dict[Coordinate, float] = {}

        if direction is not None:
            for cell, weight in self.probabilities.items():
                destination = cell.shifted(direction)
                target = (
                    destination
                    if self.board.contains(destination)
                    and not self.board.is_blocked(destination)
                    else cell  # an illegal step means they could not have moved
                )
                moved[target] = moved.get(target, 0.0) + weight
        else:
            for cell, weight in self.probabilities.items():
                options = [cell] + [
                    n
                    for d in ORTHOGONAL_DIRECTIONS
                    if self.board.is_passable(n := cell.shifted(d))
                ]
                share = weight / len(options)
                for option in options:
                    moved[option] = moved.get(option, 0.0) + share

        self.probabilities = moved
        self.exclude_impossible()

    def update_from_scent(self, scent: ScentField, *, weight: float = 1.0) -> None:
        """Correct the distribution using the opponent's scent field.

        A strong trail in a cell raises the odds the opponent was recently at or
        near it. The likelihood is ``1 + weight * intensity`` rather than the
        intensity itself, so a cell with no scent is merely unremarkable rather
        than impossible -- the trail decays, and absence of scent is weak
        evidence, not proof.
        """
        if not scent.values:
            return
        for cell in list(self.probabilities):
            self.probabilities[cell] *= 1.0 + weight * scent.intensity_at(cell)
        self.normalise()

    def blur(self, amount: float = 0.05) -> None:
        """Mix in a little uniform mass.

        Keeps the distribution from collapsing to a point that later evidence
        cannot move -- the same reason the scent model decays rather than
        accumulating forever.
        """
        if amount <= 0.0:
            return
        uniform = BeliefMap.uniform(self.board).probabilities
        for cell, share in uniform.items():
            self.probabilities[cell] = (1.0 - amount) * self.probabilities.get(
                cell, 0.0
            ) + amount * share
        self.normalise()
