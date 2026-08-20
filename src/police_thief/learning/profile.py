"""Learning profile schema: bounded, versioned, aggregate opponent tendencies.

A profile never stores a raw trajectory or a single game's verbatim events --
only bounded moving averages over ``games_seen`` completed matches, so one
unusual game cannot swing behaviour on its own (sprint requirement).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1

_DIRECTIONS = ("N", "S", "E", "W")

# How quickly a new match's evidence overwrites the running average -- a
# small, fixed EMA rate, deliberately not itself "learned".
_EMA_RATE = 0.25

# Confidence saturates once enough games have been seen that one more game
# would not meaningfully change the average.
_CONFIDENCE_SATURATION_GAMES = 8


@dataclass
class LearningProfile:
    """One profile: either the global aggregate or one opponent's."""

    schema_version: int = SCHEMA_VERSION
    games_seen: int = 0
    sample_count: int = 0
    last_updated: str = ""
    direction_bias: dict[str, float] = field(
        default_factory=lambda: dict.fromkeys(_DIRECTIONS, 0.0)
    )
    barrier_rate: float = 0.0
    avg_turns: float = 0.0
    technical_loss_rate: float = 0.0

    def confidence(self) -> float:
        """0..1, saturating -- how much this profile should be trusted."""
        return min(1.0, self.sample_count / _CONFIDENCE_SATURATION_GAMES)

    def update(
        self,
        *,
        direction_bias: dict[str, float],
        barrier_rate: float,
        turns_played: int,
        was_technical_loss: bool,
    ) -> None:
        """Fold one completed, trustworthy match in via a bounded EMA.

        Called only for matches the caller has already judged trustworthy
        enough to learn from (``run.py``/``learning/integration.py`` decide
        that; this method just does the bounded blend).
        """
        rate = _EMA_RATE if self.sample_count > 0 else 1.0
        for d in _DIRECTIONS:
            observed = max(0.0, min(1.0, direction_bias.get(d, 0.0)))
            self.direction_bias[d] = (1 - rate) * self.direction_bias[d] + rate * observed
        self.barrier_rate = (1 - rate) * self.barrier_rate + rate * max(
            0.0, min(1.0, barrier_rate)
        )
        self.avg_turns = (1 - rate) * self.avg_turns + rate * max(0, turns_played)
        loss_signal = 1.0 if was_technical_loss else 0.0
        self.technical_loss_rate = (1 - rate) * self.technical_loss_rate + rate * loss_signal

        self.sample_count += 1
        self.games_seen += 1
        self.last_updated = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearningProfile:
        """Best-effort reconstruction. Unknown/missing keys fall back to
        defaults rather than raising -- corruption must never crash a match
        (see ``store.py``, which is what actually catches parse failures)."""
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        profile = cls(**known)
        for d in _DIRECTIONS:
            profile.direction_bias.setdefault(d, 0.0)
        return profile
