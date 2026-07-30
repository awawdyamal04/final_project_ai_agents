"""The board: dimensions, bounds, and the barrier set.

Immutable. Placing a barrier returns a *new* board, which keeps the whole domain
free of in-place mutation and makes "a barrier is irreversible" (PDF p. 37) a
property of the type rather than a discipline.

Barriers live here rather than in ``LocalState`` because they are **public**: the
cop must truthfully declare every placement and its exact location (E-15, E-16),
so both peers converge on an identical barrier set. Holding them on the board is
therefore not a leak -- it is shared knowledge the rules require.

The PDF defines no pre-placed static obstacles. The only impassable cells are
barriers the cop places during play, so the board has no separate obstacle
concept; inventing one would be inventing a requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Iterator

from police_thief.config.models import SharedConfig
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ORTHOGONAL_DIRECTIONS, Direction
from police_thief.domain.exceptions import InvalidCoordinateError


@dataclass(frozen=True, slots=True)
class Board:
    """A square grid with a set of permanent barriers.

    Every dimension comes from :class:`SharedConfig`. No Appendix F literal
    appears here -- see :mod:`police_thief.config.policy`, which is the only
    module permitted to carry one.
    """

    size: int
    """Side length -- ``grid_size``, a MINIMUM parameter (7 or larger)."""

    origin_index: int
    """``axis_start_index`` -- the number each axis starts counting from."""

    barriers: frozenset[Coordinate] = field(default_factory=frozenset)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls, config: SharedConfig, barriers: Iterable[Coordinate] = ()
    ) -> Board:
        return cls(
            size=config.board_and_agents.grid_size,
            origin_index=config.board_and_agents.axis_start_index,
            barriers=frozenset(barriers),
        )

    # ------------------------------------------------------------------
    # Bounds
    # ------------------------------------------------------------------

    @property
    def min_index(self) -> int:
        return self.origin_index

    @property
    def max_index(self) -> int:
        """Highest valid index on either axis (inclusive)."""
        return self.origin_index + self.size - 1

    def contains(self, cell: Coordinate) -> bool:
        return (
            self.min_index <= cell.row <= self.max_index
            and self.min_index <= cell.col <= self.max_index
        )

    def require_contains(self, cell: Coordinate) -> None:
        if not self.contains(cell):
            raise InvalidCoordinateError(
                f"{cell} is outside the {self.size}x{self.size} board "
                f"(indices {self.min_index}..{self.max_index})"
            )

    # ------------------------------------------------------------------
    # Occupancy
    # ------------------------------------------------------------------

    def is_blocked(self, cell: Coordinate) -> bool:
        """True when a barrier occupies ``cell``. Blocks both roles alike."""
        return cell in self.barriers

    def is_passable(self, cell: Coordinate) -> bool:
        """True when ``cell`` is on the board and free of barriers."""
        return self.contains(cell) and not self.is_blocked(cell)

    def with_barrier(self, cell: Coordinate) -> Board:
        """Return a new board with ``cell`` permanently blocked.

        Callers must have validated the placement first
        (:mod:`police_thief.domain.rules`). This method enforces only what the
        board itself can know: the cell is on the board and not already blocked.
        """
        self.require_contains(cell)
        if self.is_blocked(cell):
            raise InvalidCoordinateError(f"{cell} already holds a barrier")
        return replace(self, barriers=self.barriers | {cell})

    # ------------------------------------------------------------------
    # Deterministic queries
    # ------------------------------------------------------------------

    def neighbours(self, cell: Coordinate) -> tuple[Coordinate, ...]:
        """The four orthogonal neighbours, on the board, in fixed N/S/E/W order.

        Barriers are *not* filtered out -- callers that care about passability
        ask for it. Keeping the two notions separate is what lets E-47 be stated
        precisely: a trapped thief has neighbours, but none of them passable.
        """
        return tuple(
            neighbour
            for direction in ORTHOGONAL_DIRECTIONS
            if self.contains(neighbour := cell.shifted(direction))
        )

    def passable_neighbours(self, cell: Coordinate) -> tuple[Coordinate, ...]:
        return tuple(n for n in self.neighbours(cell) if not self.is_blocked(n))

    def placement_targets(self, cell: Coordinate) -> tuple[Coordinate, ...]:
        """Cells a cop standing at ``cell`` could target with a barrier.

        PDF p. 37: "any cell within one step of it -- the cell it stands on
        itself, or one of the four orthogonally adjacent cells". Own cell first,
        then N/S/E/W, so enumeration is deterministic. Already-blocked cells are
        filtered; the quota and the actor's role are checked elsewhere.
        """
        candidates = (cell, *(cell.shifted(d) for d in ORTHOGONAL_DIRECTIONS))
        return tuple(
            candidate
            for candidate in candidates
            if self.contains(candidate) and not self.is_blocked(candidate)
        )

    def all_cells(self) -> Iterator[Coordinate]:
        """Every cell, row-major, for deterministic iteration."""
        for row in range(self.min_index, self.max_index + 1):
            for col in range(self.min_index, self.max_index + 1):
                yield Coordinate(row, col)

    @property
    def cell_count(self) -> int:
        return self.size * self.size

    @property
    def barrier_count(self) -> int:
        return len(self.barriers)

    def direction_between(
        self, origin: Coordinate, destination: Coordinate
    ) -> Direction | None:
        """The single direction taking ``origin`` to ``destination``, if any.

        Returns ``None`` when the two cells are not one orthogonal step apart --
        including for diagonals, which have no representation in
        :class:`Direction` at all.
        """
        if origin == destination:
            return Direction.STAY
        for direction in ORTHOGONAL_DIRECTIONS:
            if origin.shifted(direction) == destination:
                return direction
        return None
