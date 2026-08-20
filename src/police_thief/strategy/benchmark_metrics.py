"""Aggregate many :class:`MatchStats` into the competitive sprint's required
benchmark metrics: win rates, terminal-turn statistics, barrier efficiency,
capture-mode breakdown, invalid-action count, mobility and result
distribution.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from police_thief.domain.enums import CaptureReason, Role, TerminalReason
from police_thief.strategy.benchmark_match import MatchStats


@dataclass
class MatchupSummary:
    """Running totals for one cop/thief pairing across many games."""

    label: str
    games: int = 0
    police_wins: int = 0
    thief_wins: int = 0
    technical_losses: int = 0
    turns: list[int] = field(default_factory=list)
    barriers_placed: list[int] = field(default_factory=list)
    trapped_captures: int = 0
    barrier_captures: int = 0
    movement_captures: int = 0
    invalid_actions: int = 0
    cop_mobility: list[float] = field(default_factory=list)
    thief_mobility: list[float] = field(default_factory=list)
    result_counts: dict[str, int] = field(default_factory=dict)

    def add(self, stats: MatchStats) -> None:
        terminal = stats.outcome.terminal
        self.games += 1
        self.turns.append(terminal.turn)
        self.barriers_placed.append(stats.outcome.cop_state.barriers_placed)
        self.invalid_actions += stats.invalid_actions
        self.cop_mobility.append(stats.avg_cop_mobility)
        self.thief_mobility.append(stats.avg_thief_mobility)

        key = terminal.reason.value
        self.result_counts[key] = self.result_counts.get(key, 0) + 1

        if terminal.winner is Role.POLICE:
            self.police_wins += 1
        elif terminal.winner is Role.THIEF:
            self.thief_wins += 1
        else:
            self.technical_losses += 1

        if terminal.reason is TerminalReason.CAPTURE:
            if terminal.capture_reason is CaptureReason.THIEF_HAS_NO_LEGAL_MOVE:
                self.trapped_captures += 1
            elif terminal.capture_reason is CaptureReason.BARRIER_ON_THIEF:
                self.barrier_captures += 1
                self.trapped_captures += 1
            elif terminal.capture_reason is CaptureReason.COP_LANDED_ON_THIEF:
                self.movement_captures += 1

    def to_dict(self) -> dict:
        n = max(1, self.games)
        total_barriers = sum(self.barriers_placed) or 1
        return {
            "label": self.label,
            "games": self.games,
            "police_win_rate": self.police_wins / n,
            "thief_win_rate": self.thief_wins / n,
            "technical_loss_rate": self.technical_losses / n,
            "avg_terminal_turn": sum(self.turns) / n,
            "median_terminal_turn": (
                statistics.median(self.turns) if self.turns else 0
            ),
            "barrier_efficiency": self.trapped_captures / total_barriers,
            "trapped_captures": self.trapped_captures,
            "barrier_captures": self.barrier_captures,
            "movement_captures": self.movement_captures,
            "invalid_actions": self.invalid_actions,
            "avg_cop_mobility": sum(self.cop_mobility) / n,
            "avg_thief_mobility": sum(self.thief_mobility) / n,
            "result_distribution": dict(self.result_counts),
        }
