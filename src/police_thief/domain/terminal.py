"""Terminal conditions and the structured result of a finished sub-game."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.domain.enums import CaptureReason, Role, TerminalReason


@dataclass(frozen=True, slots=True)
class TerminalResult:
    """Why and when a sub-game ended.

    ``winner`` is ``None`` for a technical loss, which zeroes both sides
    (Ch. 3 table 2, PDF p. 38) -- deliberately, so neither side gains by
    stalling.
    """

    reason: TerminalReason
    turn: int
    winner: Role | None = None
    capture_reason: CaptureReason | None = None

    @property
    def is_capture(self) -> bool:
        return self.reason is TerminalReason.CAPTURE

    @property
    def is_survival(self) -> bool:
        return self.reason in (
            TerminalReason.SURVIVAL,
            TerminalReason.MAX_MOVES_REACHED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason.value,
            "turn": self.turn,
            "winner": self.winner.value if self.winner else None,
            "capture_reason": (
                self.capture_reason.value if self.capture_reason else None
            ),
        }


def capture(turn: int, reason: CaptureReason) -> TerminalResult:
    return TerminalResult(
        reason=TerminalReason.CAPTURE,
        turn=turn,
        winner=Role.POLICE,
        capture_reason=reason,
    )


def survival(turn: int) -> TerminalResult:
    return TerminalResult(
        reason=TerminalReason.SURVIVAL, turn=turn, winner=Role.THIEF
    )


def max_moves_reached(turn: int) -> TerminalResult:
    """The move ceiling was hit without capture.

    Phase 0 validation guarantees ``survival_threshold <= max_moves``, so
    survival fires first and this is unreachable in a valid configuration. It
    exists so that a loop bound can never be reached without a stated reason --
    an unexplained stop is a hang wearing a disguise.

    Scored as survival: the thief evaded for the whole sub-game, which is what
    the scoring table rewards.
    """
    return TerminalResult(
        reason=TerminalReason.MAX_MOVES_REACHED, turn=turn, winner=Role.THIEF
    )


def technical_loss(turn: int) -> TerminalResult:
    """Both sides score zero.

    Ch. 3 (PDF p. 38): a side crashes, exceeds time, or performs a cryptographic
    forgery. Phase 1 never raises this -- crashes, deadlines and forgery all
    belong to Phases 2 and 5 -- but the outcome is modelled here so scoring is
    complete and the later phases have somewhere to put it.
    """
    return TerminalResult(reason=TerminalReason.TECHNICAL_LOSS, turn=turn)


def evaluate_survival(turn: int, config: SharedConfig) -> TerminalResult | None:
    """Has the thief survived long enough to win?

    A "step" is counted as a completed **full turn** -- both peers having acted
    -- because scent decay is defined per full turn (Ch. 4, PDF p. 43), which
    makes the full turn the specification's own unit of time. Recorded as
    DECISIONS.md D-27.
    """
    if turn >= config.movement_and_barriers.survival_threshold:
        return survival(turn)
    return None


def evaluate_move_ceiling(
    turn: int, config: SharedConfig
) -> TerminalResult | None:
    if turn >= config.movement_and_barriers.max_moves:
        return max_moves_reached(turn)
    return None
