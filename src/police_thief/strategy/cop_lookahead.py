"""BFS distance and trap-value helpers for the belief-driven cop strategy
(competitive strategy sprint -- "shallow adversarial lookahead").

Pure functions over the board and belief map only. No opponent coordinate
crosses these functions, only candidate cells and probability mass the
belief map already legitimately holds -- the same information
:class:`police_thief.strategy.base.LocalView` exposes to every strategy.
"""

from __future__ import annotations

from collections import deque

from police_thief.domain.belief import BeliefMap
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate


def bfs_distances(
    board: Board, origin: Coordinate, horizon: int
) -> dict[Coordinate, int]:
    """Shortest passable-cell distance from ``origin``, capped at ``horizon``."""
    distances = {origin: 0}
    frontier: deque[Coordinate] = deque([origin])
    while frontier:
        cell = frontier.popleft()
        depth = distances[cell]
        if depth >= horizon:
            continue
        for neighbour in board.passable_neighbours(cell):
            if neighbour not in distances:
                distances[neighbour] = depth + 1
                frontier.append(neighbour)
    return distances


def top_belief_cells(belief: BeliefMap, k: int) -> list[tuple[Coordinate, float]]:
    """The ``k`` most probable cells, mass descending, deterministic ties."""
    ranked = sorted(
        belief.probabilities.items(),
        key=lambda item: (-item[1], item[0].row, item[0].col),
    )
    return [(cell, mass) for cell, mass in ranked if mass > 1e-6][:k]


def predicted_evasion(board: Board, believed_cell: Coordinate, threat: Coordinate) -> Coordinate:
    """Where a rational thief most plausibly flees to from ``believed_cell``
    once the cop reaches ``threat`` -- the same "maximise distance, prefer
    more exits" principle the baseline thief scores by, used here only as a
    *prediction* for one-ply lookahead. Never a claim about the opponent's
    real choice, and never a read of its true position: ``believed_cell`` is
    already this peer's own uncertain belief, nothing more.
    """
    options = (believed_cell, *board.passable_neighbours(believed_cell))
    return max(
        options,
        key=lambda c: (
            c.manhattan_distance_to(threat),
            len(board.passable_neighbours(c)),
            -c.row,
            -c.col,
        ),
    )


def capture_soon_score(
    board: Board,
    destination: Coordinate,
    belief: BeliefMap,
    top_k: int,
    horizon: int,
) -> float:
    """Expected value of closing in on likely thief cells over a few turns.

    For each of the top-``k`` believed cells, first predicts the one-ply
    evasion (:func:`predicted_evasion`) rather than scoring against where the
    thief currently stands -- an adversarial lookahead, not just a static
    chase -- then weights that predicted cell's distance from ``destination``
    by the believed cell's probability mass.
    """
    distances = bfs_distances(board, destination, horizon)
    total = 0.0
    for cell, mass in top_belief_cells(belief, top_k):
        evasion = predicted_evasion(board, cell, destination)
        distance = distances.get(evasion, horizon + 1)
        total += mass * (1.0 - distance / (horizon + 1))
    return total


def barrier_trap_value(board: Board, target: Coordinate) -> float:
    """How much closer to a full trap a barrier at one of ``target``'s exits
    would leave it.

    Zero remaining exits after the placement is worth the most (an outright
    trap under E-47); each exit still open afterwards is worth progressively
    less.
    """
    escapes = board.passable_neighbours(target)
    remaining = max(0, len(escapes) - 1)
    return 4.0 - remaining
