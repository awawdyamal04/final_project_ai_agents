"""Pheromone / scent field.

Physics from SharedConfig (Appendix F table 16, all three FIXED):
``pheromone_center_intensity`` 0.9, ``pheromone_decay`` 0.10,
``pheromone_grid_size`` 5.

Emission: a window of side ``pheromone_grid_size`` centred on the agent, the
centre cell at full intensity, falling off radially.

Decay, once per **full turn** (after both peers have moved):

    tau(t+1) = max(0, (1 - rho) * tau(t) + delta_tau)

Two properties the specification is emphatic about, and which shape the API:

* **Scent cannot lie.** It is emitted by the act of occupying a cell. There is
  no method here to deposit scent anywhere but the emitter's own position, so
  planting a false trail is not expressible.
* **Each peer reads only its opponent's field**, never its own. Two separate
  :class:`ScentField` objects are therefore maintained, not one shared grid.

The radial falloff is Gaussian with ``SIGMA = 1.15``, chosen because it
reproduces the tabulated emission field in the PDF's figure to two decimal
places (0.90 / 0.62 / 0.42 / 0.20 / 0.14 / 0.04). The prose fixes only the
centre value and the word "radial", so the exact curve is a project decision
(DECISIONS.md D-39) and is one of the things E-23 requires to be exchanged and
locked with the opponent before a series.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from police_thief.config.models import SharedConfig
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate

SIGMA = 1.15
"""Gaussian width, fitted to the PDF's tabulated emission field."""


@dataclass(frozen=True, slots=True)
class ScentModel:
    """The agreed emission and decay physics."""

    center_intensity: float
    decay: float
    window: int
    sigma: float = SIGMA

    @classmethod
    def from_config(cls, config: SharedConfig) -> ScentModel:
        p = config.pheromones
        return cls(
            center_intensity=p.pheromone_center_intensity,
            decay=p.pheromone_decay,
            window=p.pheromone_grid_size,
        )

    @property
    def radius(self) -> int:
        return self.window // 2

    def emission_at(self, offset_sq: int) -> float:
        """Emitted intensity at squared distance ``offset_sq`` from the centre."""
        return self.center_intensity * math.exp(
            -offset_sq / (2.0 * self.sigma * self.sigma)
        )

    def numeric_example(self) -> dict[str, float]:
        """The concrete example E-23 requires to be exchanged and locked."""
        return {
            "centre": round(self.center_intensity, 4),
            "after_one_decay_turn": round(
                self.center_intensity * (1.0 - self.decay), 4
            ),
            "orthogonal_neighbour": round(self.emission_at(1), 4),
            "diagonal_neighbour": round(self.emission_at(2), 4),
        }


@dataclass
class ScentField:
    """One emitter's decaying trail over the board.

    Mutable and cheap: a dict of cell to intensity, with zeros dropped so an
    untouched cell is simply absent rather than stored as 0.0.
    """

    model: ScentModel
    board: Board
    values: dict[Coordinate, float] = field(default_factory=dict)

    @classmethod
    def for_config(cls, config: SharedConfig, board: Board) -> ScentField:
        return cls(model=ScentModel.from_config(config), board=board)

    def intensity_at(self, cell: Coordinate) -> float:
        return self.values.get(cell, 0.0)

    def emit(self, centre: Coordinate) -> None:
        """Deposit scent around ``centre``.

        The only way scent enters the field, and it takes the emitter's own
        cell. There is deliberately no way to deposit a trail elsewhere.
        """
        radius = self.model.radius
        for d_row in range(-radius, radius + 1):
            for d_col in range(-radius, radius + 1):
                cell = Coordinate(centre.row + d_row, centre.col + d_col)
                if not self.board.contains(cell):
                    continue
                added = self.model.emission_at(d_row * d_row + d_col * d_col)
                if added <= 0.0:
                    continue
                self.values[cell] = self.values.get(cell, 0.0) + added

    def decay(self) -> None:
        """Apply one full-turn decay pass, clamped at zero."""
        keep = 1.0 - self.model.decay
        decayed: dict[Coordinate, float] = {}
        for cell, value in self.values.items():
            new = max(0.0, keep * value)
            if new > 1e-9:
                decayed[cell] = new
        self.values = decayed

    def advance_turn(self, centre: Coordinate) -> None:
        """Emit at ``centre``, then decay -- one full turn for this emitter."""
        self.emit(centre)
        self.decay()

    def peak(self) -> tuple[Coordinate, float] | None:
        """The strongest cell, ties broken by coordinate order for determinism."""
        if not self.values:
            return None
        cell = max(self.values, key=lambda c: (self.values[c], -c.row, -c.col))
        return cell, self.values[cell]

    def total(self) -> float:
        return sum(self.values.values())
