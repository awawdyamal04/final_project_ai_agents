"""Domain events emitted by a transition.

Deterministic and ordered: the same inputs produce the same events in the same
sequence. Phase 5 will seal these into the audit log, where any divergence
between the two peers' records becomes a hash mismatch and a technical loss --
so "roughly the same events" is not good enough.

Events carry only what the emitting peer legitimately knows. There is no
``OpponentMoved`` event, because a peer does not observe its opponent's
movement; what it observes is a decaying scent field and a hint that may be a
lie, and both arrive in Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role


@dataclass(frozen=True, slots=True)
class AgentMoved:
    """This peer relocated, or stood still."""

    role: Role
    direction: Direction
    origin: Coordinate
    destination: Coordinate
    turn: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "agent_moved",
            "role": self.role.value,
            "direction": self.direction.value,
            "origin": self.origin.as_list(),
            "destination": self.destination.as_list(),
            "turn": self.turn,
        }


@dataclass(frozen=True, slots=True)
class BarrierPlaced:
    """The cop blocked a cell permanently.

    Public by obligation: the cop must truthfully declare every placement and
    its exact location, and may not place one covertly (E-15, E-16). This event
    is the domain-level form of that declaration.
    """

    role: Role
    cell: Coordinate
    turn: int
    barriers_placed: int
    barriers_remaining: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "barrier_placed",
            "role": self.role.value,
            "cell": self.cell.as_list(),
            "turn": self.turn,
            "barriers_placed": self.barriers_placed,
            "barriers_remaining": self.barriers_remaining,
        }


@dataclass(frozen=True, slots=True)
class SubGameFinished:
    """The sub-game reached a terminal state."""

    reason: str
    winner: Role | None
    turn: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "sub_game_finished",
            "reason": self.reason,
            "winner": self.winner.value if self.winner else None,
            "turn": self.turn,
        }


DomainEvent = AgentMoved | BarrierPlaced | SubGameFinished
