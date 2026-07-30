"""What a peer may do on its turn.

Two actions, and they are alternatives: the cop may move *or* forgo movement to
place a barrier (PDF p. 37). Modelling placement as its own action rather than
as a flag on a move keeps that exclusivity in the type system -- there is no way
to express "move and place", because the rule does not permit it.

The PDF does not specify a wire encoding for actions. The minimal internal
representation below is a project decision (DECISIONS.md D-25); the wire form
belongs to Phase 2 and is negotiated with the opponent.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import ActionKind, Direction


@dataclass(frozen=True, slots=True)
class Move:
    """Relocate one orthogonal step, or stand still.

    ``STAY`` is a legal action in its own right: Appendix F fixes ``move_set``
    at four directions "+ standing" (table 15 row 1). It is not the same as
    forgoing movement to place a barrier -- a cop that stays put has still used
    its turn without placing anything.
    """

    direction: Direction
    kind: ActionKind = ActionKind.MOVE

    def __str__(self) -> str:
        return f"MOVE:{self.direction.value}"


@dataclass(frozen=True, slots=True)
class PlaceBarrier:
    """Forgo movement and block a cell permanently.

    Cop-only. The target must be the cop's own cell or an orthogonal neighbour.
    The cell is named explicitly because the cop must declare every placement
    and its exact location, and may not place one covertly (E-15, E-16).
    """

    cell: Coordinate
    kind: ActionKind = ActionKind.PLACE_BARRIER

    def __str__(self) -> str:
        return f"BARRIER:{self.cell.row},{self.cell.col}"


Action = Move | PlaceBarrier


def describe(action: Action) -> str:
    """Stable text form, for logs and test assertions."""
    return str(action)
