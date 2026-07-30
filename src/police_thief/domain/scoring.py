"""Scoring.

One entry point, :func:`calculate_score`. Score arithmetic appears nowhere else
in the domain -- scattering it through movement or capture code would make
E-48 ("score every end scenario according to the scoring table") unverifiable,
because there would be no single place to check.

Every value comes from :class:`SharedConfig`. No Appendix F literal appears
here.

Scope: this module scores **one sub-game**. The tie rule is *not* a sub-game
outcome -- the PDF defines it over "the accumulated score of **all** sub-games"
against an opponent (Ch. 9, PDF p. 87) -- so it is a match-level function,
provided separately below and left unused until league aggregation in Phase 9.
Diversity reward is likewise league-level and belongs to that phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.domain.enums import Role, TerminalReason
from police_thief.domain.terminal import TerminalResult


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Points for both sides from one finished sub-game."""

    cop: int
    thief: int
    reason: TerminalReason

    def for_role(self, role: Role) -> int:
        return self.cop if role is Role.POLICE else self.thief

    @property
    def total(self) -> int:
        return self.cop + self.thief

    def to_dict(self) -> dict[str, Any]:
        return {"cop": self.cop, "thief": self.thief, "reason": self.reason.value}


def calculate_score(
    terminal: TerminalResult, config: SharedConfig
) -> ScoreResult:
    """Score a finished sub-game from the shared scoring table.

    The asymmetry is deliberate and comes straight from the PDF (Ch. 3, PDF
    pp. 38-39): capture gives the cop its highest reward, prolonged survival
    gives the thief *its* highest reward, and a technical loss zeroes both --
    so neither side profits from breaking the protocol rather than losing on
    the board.
    """
    scoring = config.scoring

    if terminal.reason is TerminalReason.CAPTURE:
        return ScoreResult(
            cop=scoring.capture_cop,
            thief=scoring.capture_thief,
            reason=terminal.reason,
        )

    if terminal.reason in (
        TerminalReason.SURVIVAL,
        TerminalReason.MAX_MOVES_REACHED,
    ):
        return ScoreResult(
            cop=scoring.survival_cop,
            thief=scoring.survival_thief,
            reason=terminal.reason,
        )

    if terminal.reason is TerminalReason.TECHNICAL_LOSS:
        return ScoreResult(
            cop=scoring.technical_loss,
            thief=scoring.technical_loss,
            reason=terminal.reason,
        )

    raise ValueError(  # pragma: no cover - the enum is closed
        f"unscored terminal reason: {terminal.reason}"
    )


# ----------------------------------------------------------------------
# Match level -- not a sub-game outcome
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MatchScore:
    """Cumulative score across all sub-games against one opponent."""

    cop: int
    thief: int
    tied: bool


def apply_tie_rule(
    cop_total: int, thief_total: int, config: SharedConfig
) -> MatchScore:
    """Apply the tie rule to a whole match.

    Ch. 9 (PDF p. 87): if the accumulated score of **all** sub-games between a
    pair of teams ends level, each team receives ``tie_score``.

    Match-level, not sub-game-level, which is why it is not part of
    :func:`calculate_score`. Provided here so the rule lives beside the rest of
    the scoring table rather than being rediscovered in Phase 9; league
    aggregation itself -- diversity reward, counted-match ledger -- belongs to
    that phase.
    """
    if cop_total == thief_total:
        tie = config.scoring.tie_score
        return MatchScore(cop=tie, thief=tie, tied=True)
    return MatchScore(cop=cop_total, thief=thief_total, tied=False)
