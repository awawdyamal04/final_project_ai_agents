"""Extract only legally observable match features for learning.

BOUNDARY (see ``learning/__init__.py``): this module accepts an
:class:`~police_thief.strategy.opponent_model.OpponentModel` -- itself built
only from ``LocalView`` (own belief drift, own board's public barriers, see
``strategy/opponent_model.py``) -- plus this peer's own honest bookkeeping
about *its own* match (turns played, its own exit status, its own
capture_claim verdict). It never accepts or imports anything from
``police_thief.replay`` or ``police_thief.sim.harness``, and there is no
parameter here through which an opponent coordinate could arrive.
"""

from __future__ import annotations

from dataclasses import dataclass

from police_thief.domain.enums import Direction, Role
from police_thief.strategy.opponent_model import OpponentModel

# A completed match is judged trustworthy enough to learn from only once the
# protocol reached a clean finish -- see ``exit_status`` values printed by
# ``peer/run.py``'s ``_print_match_summary``.
TRUSTWORTHY_EXIT_STATUS = "MATCH COMPLETE"


@dataclass(frozen=True)
class MatchObservation:
    """One completed match's worth of legal, aggregate evidence.

    ``barrier_rate`` is an *opponent* tendency, and barrier placement is
    cop-exclusive (PDF p. 37): from the thief's own model it legitimately
    reads the cop's placement frequency, but from the cop's own model any
    board-barrier growth it can see is necessarily *its own* placements --
    there is no such thing as the thief's barrier rate, because the thief
    structurally cannot place one. ``extract_observation`` enforces this: a
    police-role observation always carries ``barrier_rate=0.0`` (the true,
    trivial fact that this opponent never barriers), never the cop's own
    rate mislabelled as the opponent's.
    """

    opponent_key: str
    direction_bias: dict[str, float]
    barrier_rate: float
    turns_played: int
    was_technical_loss: bool
    trustworthy: bool


def extract_observation(
    *,
    role: Role,
    opponent_key: str,
    opponent_model: OpponentModel,
    turns_played: int,
    exit_status: str,
) -> MatchObservation:
    """Build the observation this match is allowed to teach the profiles.

    ``opponent_model`` already normalises its own tallies (see
    ``OpponentModel.direction_bias``/``barrier_rate``); this function
    reshapes that into the flat, JSON-friendly form ``profile.py`` expects,
    decides whether the match is trustworthy enough to learn from at all (a
    technical loss or an aborted handshake carries no reliable signal about
    the opponent's *style*, only about this run's plumbing, so it must not
    poison the profile -- sprint requirement), and -- see
    :class:`MatchObservation` -- suppresses ``barrier_rate`` for the police
    role, where the underlying board-growth signal is this peer's own
    placements rather than the opponent's.
    """
    direction_bias = {
        direction.value: opponent_model.direction_bias(direction)
        for direction in (Direction.N, Direction.S, Direction.E, Direction.W)
    }
    trustworthy = exit_status == TRUSTWORTHY_EXIT_STATUS and turns_played > 0
    barrier_rate = opponent_model.barrier_rate() if role is Role.THIEF else 0.0
    return MatchObservation(
        opponent_key=opponent_key,
        direction_bias=direction_bias,
        barrier_rate=barrier_rate,
        turns_played=turns_played,
        was_technical_loss=exit_status != TRUSTWORTHY_EXIT_STATUS,
        trustworthy=trustworthy,
    )
