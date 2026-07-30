"""Board coordinates.

Cells are addressed ``(row, col)``, following the Chapter 3 text (PDF p. 34).
Chapter 6's belief-map figure labels its axes ``x (column)`` and ``y (row)``,
which is the same information in the other order; the text wins, since diagrams
are not binding (PDF p. 4). See OPEN_QUESTIONS.md Q-10.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.domain.enums import Direction


@dataclass(frozen=True, slots=True, order=True)
class Coordinate:
    """An immutable board cell.

    Ordered so that collections of coordinates can be sorted into a stable
    sequence -- determinism in legal-action generation and in logs depends on
    it, since two peers must enumerate identically.
    """

    row: int
    col: int

    def shifted(self, direction: Direction) -> Coordinate:
        """Return the neighbour in ``direction``.

        Purely arithmetic: it does not know the board and cannot tell whether
        the result is on it. Bounds and barriers are the board's business.
        """
        d_row, d_col = direction.delta
        return Coordinate(self.row + d_row, self.col + d_col)

    def manhattan_distance_to(self, other: Coordinate) -> int:
        """Manhattan distance -- the admissible metric for orthogonal movement.

        Used by the Phase 3 strategy layer; defined here because it is a
        property of the coordinate system, not of any policy.
        """
        return abs(self.row - other.row) + abs(self.col - other.col)

    def is_orthogonally_adjacent_to(self, other: Coordinate) -> bool:
        """True when ``other`` is exactly one orthogonal step away."""
        return self.manhattan_distance_to(other) == 1

    def as_tuple(self) -> tuple[int, int]:
        return (self.row, self.col)

    def as_list(self) -> list[int]:
        """JSON-friendly form, matching the config's ``[row, col]`` shape."""
        return [self.row, self.col]

    @classmethod
    def from_pair(cls, pair: tuple[int, int] | list[int]) -> Coordinate:
        row, col = pair
        return cls(int(row), int(col))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"({self.row},{self.col})"
