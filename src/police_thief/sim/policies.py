"""Trivial deterministic policies, for the Phase 1 harness.

**Not strategy.** Real movement policy -- belief maps, Manhattan pursuit,
barrier planning -- is Phase 3 and Phase 4, and is described by the PDF as "the
core of the grade". These exist only to drive a sub-game to completion so the
domain can be exercised.

Every policy here is deterministic and blind: it sees only its own
:class:`LocalState`, which is all a live peer ever has. None of them takes an
opponent position, because none of them could.
"""

from __future__ import annotations

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import Action, Move
from police_thief.domain.enums import Direction
from police_thief.domain.rules import legal_actions, legal_moves
from police_thief.domain.state import LocalState


def stay_put(state: LocalState, config: SharedConfig) -> Action:
    """Always stand still. The simplest way to reach the survival threshold."""
    return Move(Direction.STAY)


def first_legal_move(state: LocalState, config: SharedConfig) -> Action:
    """Take the first legal move in the canonical order.

    Deterministic by construction: :func:`legal_moves` returns a fixed order,
    so the same state always yields the same action.
    """
    moves = legal_moves(state, config)
    return moves[0] if moves else Move(Direction.STAY)


def cycle_directions(state: LocalState, config: SharedConfig) -> Action:
    """Walk N, S, E, W in rotation, falling back to ``STAY``.

    Uses the turn counter as the cycle index, so it is a pure function of the
    state -- replaying the same sub-game produces the same moves.
    """
    order = (Direction.N, Direction.S, Direction.E, Direction.W)
    preferred = order[state.turn % len(order)]
    legal = {move.direction for move in legal_moves(state, config)}
    if preferred in legal:
        return Move(preferred)
    for direction in order:
        if direction in legal:
            return Move(direction)
    return Move(Direction.STAY)


def first_legal_action(state: LocalState, config: SharedConfig) -> Action:
    """First legal action of any kind, moves before barrier placements."""
    actions = legal_actions(state, config)
    return actions[0] if actions else Move(Direction.STAY)
