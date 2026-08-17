"""A minimal custom brain, used only to test `load_strategy`'s import path.

Stands in for a team's own `[strategy] police_class` / `thief_class` override
(config/*.toml.example). Not part of the shipped strategy layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.domain.actions import Action, Move
from police_thief.domain.enums import Direction
from police_thief.strategy.base import LocalView


@dataclass
class DummyBrain:
    """Implements the BaseStrategy protocol: always stays put."""

    name: str = "dummy-brain"

    def choose(self, view: LocalView) -> Action:
        return Move(Direction.STAY)


class NotABrain:
    """Missing `.choose` -- used to test the protocol-conformance check."""

    name = "not-a-brain"
