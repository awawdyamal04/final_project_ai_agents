"""Tunable weights for the belief-driven cop and risk-aware thief strategies
(competitive strategy sprint).

Centralised so a parameter sweep (``scripts/strategy_sweep.py``) can vary one
place rather than editing scoring code, and so a winning configuration can be
recorded as plain JSON. Nothing here is an Appendix F parameter -- these are
strategy tuning knobs, not game physics, so they carry no MINIMUM/FIXED
status and are never read through :mod:`police_thief.config.policy`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CopWeights:
    """Scoring weights for :class:`police_thief.strategy.cop_belief.BeliefCopStrategy`."""

    capture_now: float = 12.0
    capture_soon: float = 6.0
    scent: float = 3.0
    belief: float = 8.0
    loop_penalty: float = 2.5
    edge_push: float = 1.5
    info_gain: float = 1.0
    opponent_bias: float = 0.0
    """Off by default, deliberately. Under the current reveal semantics the
    opponent's action is disclosed exactly each turn, so ``belief.peak()``
    already tracks the thief almost exactly (see the reconstruction note in
    ``strategy/tracker.py`` and OPEN_QUESTIONS.md Q-17) -- an interception
    nudge toward a noisy habitual-direction proxy then only ever competes
    with that already-accurate signal, never improves on it. Measured
    directly: raising this from 0.0 to 0.2 regressed the cop's win rate
    against the baseline thief from 100% to 55% over 40 seeded games. Kept
    as a real, working capability (and exercised by the parameter sweep) for
    if/when the reveal semantics are renegotiated to be less exact -- not
    deleted, just not trusted by default."""
    stay_penalty: float = 0.5
    near_tie_epsilon: float = 0.1
    """Kept small on purpose: measured directly (``scripts/strategy_sweep.py``
    range), a wide tie window (0.2+) let the seeded RNG pick between options
    that were *not* actually equivalent for a pursuer and cost real win rate
    (100% -> ~75-78% over 60 seeded games against the baseline thief). A
    pursuer benefits far less from unpredictability than an evader does --
    see ``ThiefWeights.near_tie_epsilon``, which stays wide -- so this only
    breaks genuine near-ties rather than gambling with real ones."""
    lookahead_top_k: int = 3
    lookahead_horizon: int = 4
    barrier_confidence: float = 0.15
    crowd_threshold: int = 3
    barrier_trap_bonus: float = 40.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CopWeights:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass(frozen=True)
class ThiefWeights:
    """Scoring weights for :class:`police_thief.strategy.thief_risk.RiskThiefStrategy`."""

    threat_distance: float = 2.0
    mobility: float = 1.5
    future_mobility: float = 0.6
    corner_penalty: float = 3.0
    barrier_confinement: float = 1.2
    scent: float = 4.0
    loop_penalty: float = 2.5
    stay_penalty: float = 1.0
    opponent_bias: float = 1.0
    near_tie_epsilon: float = 0.75

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ThiefWeights:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
