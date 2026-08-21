"""``subtractive_chebyshev_v1`` -- the reference-v3 wire's own scent model
(SPEC section 5; ``vectors/pheromone.json``, verified against that vector's
own emit/decay fixtures in ``tests/interop``).

**Deliberately isolated from** :mod:`police_thief.domain.scent`, which
implements the *book's* ``multiplicative_book_v1`` (a Gaussian radial kernel,
decayed multiplicatively once per full turn) -- a different, already-tested
model this project's native protocol never puts on the wire at all (see
``tests/interop/test_wire_shape_and_locked_models.py``). Per the task's Phase
5 instruction, only the exact model reference-v3 requires is implemented
here, and it holds its own state rather than reusing ``ScentField``'s.

Formula (matches ``vectors/pheromone.json`` exactly):
    half = grid_size // 2 ; falloff = intensity / (half + 1)
    value(cell) = round(max(0, intensity - falloff * chebyshev(cell, center)), 3)
    decay(v) = round(max(0, v - decay), 3)
Only ``value > 0`` crosses the wire, as ``{"r,c": value}``.
"""

from __future__ import annotations

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.scent import ScentField, ScentModel


def emit_v3(
    center: tuple[int, int], intensity: float, grid_size: int, board_size: int
) -> dict[str, float]:
    """One emitter's field around ``center``, clipped to the board."""
    half = grid_size // 2
    falloff = intensity / (half + 1)
    out: dict[str, float] = {}
    for d_row in range(-half, half + 1):
        for d_col in range(-half, half + 1):
            row, col = center[0] + d_row, center[1] + d_col
            if not (0 <= row < board_size and 0 <= col < board_size):
                continue
            value = round(max(0.0, intensity - falloff * max(abs(d_row), abs(d_col))), 3)
            if value > 0.0:
                out[f"{row},{col}"] = value
    return out


def decay_v3(values: dict[str, float], decay: float) -> dict[str, float]:
    """One game-step of linear decay, clamped at zero, dropping cells that
    reach it -- matching ``vectors/pheromone.json``'s ``decay`` fixtures."""
    decayed = {key: round(max(0.0, value - decay), 3) for key, value in values.items()}
    return {key: value for key, value in decayed.items() if value > 0.0}


def wire_key_to_cell(key: str) -> Coordinate:
    row, col = key.split(",", 1)
    return Coordinate(int(row), int(col))


def scent_field_from_wire(
    grid: dict[str, float], model: ScentModel, board
) -> ScentField:
    """Wrap an inbound ``smell_grid`` as a :class:`ScentField`, so this
    project's already-tested strategies (``LocalView.opponent_scent``) and
    ``BeliefMap.update_from_scent`` can read it exactly as they read a native
    field -- only the values' provenance differs."""
    values = {wire_key_to_cell(key): float(value) for key, value in grid.items()}
    return ScentField(model=model, board=board, values=values)
