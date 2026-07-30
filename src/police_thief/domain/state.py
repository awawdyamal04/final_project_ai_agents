"""The local truth of one peer.

Why this class cannot represent global truth
============================================

E-8 and E-9 carry the heaviest sanctions in the specification -- "disqualification
of the project for an illegal advantage" -- and they are the two rules a working
implementation is most likely to break by accident, because the opponent's
position is exactly what every part of the program would find convenient to
know.

So the guarantee here is structural rather than procedural. :class:`LocalState`
has **no attribute** for the opponent's position: not ``None``, not
``Optional``, not a private underscore field, not a dict entry. The attribute
does not exist. ``slots=True`` means one cannot be attached at runtime either.
A leak therefore surfaces as an ``AttributeError`` in a unit test rather than as
a subtle advantage that survives to the league.

This follows the Dec-POMDP formalism the project is built on (Ch. 1, PDF p. 21):
each agent's observation Ωᵢ is a strict subset of the true state S. An object
able to hold S would be modelling a game nobody is playing.

What the state may hold, and why each item is legal
--------------------------------------------------
* ``position`` -- the agent's *own* cell. Its own truth.
* ``board`` -- dimensions and barriers. Barriers are public: the cop must
  declare every placement and its exact location (E-15, E-16), so both peers
  converge on an identical set. Shared knowledge the rules require, not a leak.
* ``turn`` -- the local turn counter.
* ``barriers_placed`` -- how much of its own quota this peer has spent.
* ``terminal`` -- whether *this* peer considers the sub-game over.

Capture, which needs both positions, is deliberately **not** a method here. It
is evaluated by :mod:`police_thief.domain.capture`, called by an adjudicator
that holds both positions -- the test harness in Phase 1, and in the real game
the capture-claim protocol (E-21, E-22) plus the post-match replay verifier.
A live peer never computes it alone, because a live peer does not have the
inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Role
from police_thief.domain.terminal import TerminalResult

FORBIDDEN_STATE_FIELDS: frozenset[str] = frozenset(
    {
        "opponent_position",
        "opponent_cell",
        "true_opponent_position",
        "thief_position",
        "cop_position",
        "police_position",
        "global_state",
        "full_board_state",
        "world_state",
        "ground_truth",
        "both_positions",
    }
)
"""Names that must never appear on :class:`LocalState`.

Asserted by ``tests/domain/test_information_boundary.py``. A list of banned
names is weaker than the absence of the attribute itself, but it catches the
realistic regression: someone adding a field in a hurry, under a name that
sounds harmless.
"""


@dataclass(frozen=True, slots=True)
class LocalState:
    """One peer's complete view of the sub-game.

    Frozen: every transition returns a new state. Nothing mutates in place, so
    a rejected action cannot leave a half-applied change behind.
    """

    role: Role
    position: Coordinate
    board: Board
    turn: int = 0
    barriers_placed: int = 0
    terminal: TerminalResult | None = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def initial(cls, role: Role, config: SharedConfig) -> LocalState:
        """Build the opening state for ``role`` from the shared constitution.

        Reads only that role's own start cell. The other start cell is in the
        same config file -- both peers must agree on it -- but this constructor
        does not look at it, so an accidental "while we're here" leak has no
        foothold.
        """
        board_config = config.board_and_agents
        start = (
            board_config.cop_start
            if role is Role.POLICE
            else board_config.thief_start
        )
        return cls(
            role=role,
            position=Coordinate.from_pair(start),
            board=Board.from_config(config),
        )

    # ------------------------------------------------------------------
    # Derived, local-only
    # ------------------------------------------------------------------

    @property
    def is_finished(self) -> bool:
        return self.terminal is not None

    @property
    def may_place_barriers(self) -> bool:
        """Only the cop has the barrier action (PDF p. 37)."""
        return self.role is Role.POLICE

    def barriers_remaining(self, config: SharedConfig) -> int:
        if not self.may_place_barriers:
            return 0
        return config.movement_and_barriers.max_barriers - self.barriers_placed

    def with_position(self, cell: Coordinate) -> LocalState:
        return replace(self, position=cell)

    def with_board(self, board: Board) -> LocalState:
        return replace(self, board=board)

    def advanced(self) -> LocalState:
        return replace(self, turn=self.turn + 1)

    def finished(self, terminal: TerminalResult) -> LocalState:
        return replace(self, terminal=terminal)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_public_dict(self) -> dict[str, Any]:
        """A JSON-friendly view of this peer's state.

        Contains no opponent position, because the object it is built from has
        none. Asserted by
        ``test_information_boundary.py::test_serialisation_contains_no_opponent_position``.

        Not the wire format and not the log record -- those are Phase 2 and
        Phase 5 respectively, and are negotiated with the opponent.
        """
        return {
            "role": self.role.value,
            "position": self.position.as_list(),
            "turn": self.turn,
            "barriers_placed": self.barriers_placed,
            "barriers": sorted(b.as_list() for b in self.board.barriers),
            "board_size": self.board.size,
            "finished": self.is_finished,
            "terminal": self.terminal.to_dict() if self.terminal else None,
        }
