"""Strategy layer: what a peer decides, from what it is allowed to know.

Deliberately separate from transport, crypto and the domain. It receives a
:class:`~police_thief.strategy.base.LocalView` -- which has no field for the
opponent's position and no handle on any harness -- and returns one legal
action.
"""

from police_thief.strategy.base import BaseStrategy, LocalView
from police_thief.strategy.heuristics import (
    CopStrategy,
    ThiefStrategy,
    strategy_for,
)
from police_thief.strategy.tracker import OpponentTracker

__all__ = [
    "BaseStrategy",
    "CopStrategy",
    "LocalView",
    "OpponentTracker",
    "ThiefStrategy",
    "strategy_for",
]
