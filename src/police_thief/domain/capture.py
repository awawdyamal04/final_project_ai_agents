"""Capture evaluation.

**Deliberately not a method on LocalState.** Every function here needs both
agents' positions, and a live peer has only its own. Capture is therefore
evaluated by an adjudicator that legitimately holds both:

* in Phase 1, the headless test harness;
* in the real game, the capture-claim protocol (E-21, E-22), where the cop
  claims and the thief is under a cryptographic obligation to answer truthfully;
* after the match, the replay verifier, which reconstructs both trajectories
  from the logs.

Putting these functions on the state object would have required the state to
hold the opponent's position, which is exactly what E-9 forbids. The awkwardness
of passing both positions explicitly is the point: it makes the omniscient call
sites visible and countable.

The three mandatory capture conditions
--------------------------------------
1. The cop lands on the thief's cell -- Ch. 3 scoring table, PDF p. 38.
2. A barrier is placed on the cell where the thief stands -- E-46, PDF p. 149.
3. The thief has no legal move -- E-47, PDF p. 149.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.config.models import SharedConfig
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason
from police_thief.domain.rules import is_trapped
from police_thief.domain.simultaneity import (
    DEFAULT_SIMULTANEITY_POLICY,
    SimultaneityPolicy,
    TurnMovement,
)
from police_thief.domain.state import LocalState


@dataclass(frozen=True, slots=True)
class CaptureVerdict:
    """Whether a capture occurred, and on what grounds."""

    captured: bool
    reason: CaptureReason | None = None

    @classmethod
    def none(cls) -> CaptureVerdict:
        return cls(captured=False)

    @classmethod
    def by(cls, reason: CaptureReason) -> CaptureVerdict:
        return cls(captured=True, reason=reason)

    def __bool__(self) -> bool:
        return self.captured


def evaluate_barrier_capture(
    barrier_cell: Coordinate, thief_cell: Coordinate
) -> CaptureVerdict:
    """E-46: a barrier placed on the thief's cell captures it, at that moment.

    Evaluated at placement time and not deferred: the PDF says the thief "is
    captured at that moment" (PDF p. 37).
    """
    if barrier_cell == thief_cell:
        return CaptureVerdict.by(CaptureReason.BARRIER_ON_THIEF)
    return CaptureVerdict.none()


def evaluate_trapped_capture(
    thief_state: LocalState, config: SharedConfig
) -> CaptureVerdict:
    """E-47: a thief with no legal relocation is captured.

    The rule's parenthetical defines "no legal move" precisely -- *all adjacent
    cells blocked by barriers and/or board edges* (PDF p. 37) -- so ``STAY``
    does not rescue a walled-in thief. See
    :func:`police_thief.domain.rules.legal_relocations`.

    Takes the thief's own state, which contains its own position and the public
    barrier set. No opponent knowledge is required, so this is the one capture
    condition a live peer could in principle evaluate for itself.
    """
    if is_trapped(thief_state, config):
        return CaptureVerdict.by(CaptureReason.THIEF_HAS_NO_LEGAL_MOVE)
    return CaptureVerdict.none()


def evaluate_movement_capture(
    movement: TurnMovement,
    policy: SimultaneityPolicy = DEFAULT_SIMULTANEITY_POLICY,
) -> CaptureVerdict:
    """Capture arising from the turn's movement.

    Delegates to the simultaneity policy, because *which* movement patterns
    count is unresolved by the PDF -- see
    :mod:`police_thief.domain.simultaneity`.
    """
    reason = policy.resolve(movement)
    return CaptureVerdict.by(reason) if reason else CaptureVerdict.none()


def evaluate_full_turn_capture(
    movement: TurnMovement,
    thief_state: LocalState,
    config: SharedConfig,
    policy: SimultaneityPolicy = DEFAULT_SIMULTANEITY_POLICY,
) -> CaptureVerdict:
    """All movement-derived capture conditions, in a fixed order.

    Movement first, then the trapped test: a thief caught by coincidence is
    caught for that reason, not for being incidentally walled in on the same
    turn. Barrier capture (E-46) is evaluated at placement time by
    :func:`evaluate_barrier_capture` rather than here, since it does not arise
    from movement.
    """
    verdict = evaluate_movement_capture(movement, policy)
    if verdict:
        return verdict
    return evaluate_trapped_capture(thief_state, config)
