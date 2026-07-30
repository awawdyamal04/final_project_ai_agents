"""Domain errors.

One distinguishable type per failure category, so a test can assert *which* rule
was broken. Every one of these is raised *before* any state changes: an illegal
action must never leave the state partially modified, because a peer whose state
diverged mid-turn cannot be recovered by the protocol -- it can only be detected
much later, at the audit, as a hash mismatch.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every game-domain failure."""


class InvalidCoordinateError(DomainError):
    """A coordinate is malformed or outside the board."""


class IllegalActionError(DomainError):
    """Base class for a rejected action."""


class IllegalMoveError(IllegalActionError):
    """A move that the agreed physics does not permit.

    The opposing agent enforces the physics (PDF p. 38): a move outside the
    move set is rejected by the counterpart, not merely ignored.
    """


class OutOfBoundsMoveError(IllegalMoveError):
    """The move would leave the board."""


class BlockedCellError(IllegalMoveError):
    """The destination holds a barrier.

    A barrier is impassable to *both* players until the end of the game
    (PDF p. 37).
    """


class UnauthorizedBarrierActionError(IllegalActionError):
    """A role other than the cop attempted to place a barrier.

    Barrier placement is the cop's asymmetric advantage (PDF p. 37); the thief
    has no such action.
    """


class InvalidBarrierPlacementError(IllegalActionError):
    """The target cell is not a legal placement.

    Legal targets are the cop's own cell or one of the four orthogonally
    adjacent cells, on the board, and not already blocked (PDF p. 37).
    """


class BarrierQuotaExceededError(IllegalActionError):
    """The cop has already placed ``max_barriers`` barriers.

    Every placement is a resource-management decision (PDF p. 37); the quota is
    a MINIMUM parameter and comes from configuration.
    """


class GameAlreadyFinishedError(DomainError):
    """An action was attempted after the sub-game reached a terminal state."""


class InvalidTransitionError(DomainError):
    """The transition function was called with inconsistent inputs."""
