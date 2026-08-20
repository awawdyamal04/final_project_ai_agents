"""Bounded parameter adaptation around the production strategy baselines.

CURRENT PRODUCTION WEIGHTS ARE THE SAFETY BASELINE (sprint requirement).
Every function here starts from the shipped default and moves it *toward* a
profile-derived target by at most ``confidence * LEARNING_RATE`` of the
distance to that target, then hard-clips to a fixed ``[MIN, MAX]`` -- so even
a maximally confident, maximally extreme profile can only pull the result
partway, and never outside the bound. An unknown opponent (``sample_count``
0) has zero confidence and the result is the baseline, unchanged.

The cop's own production strategy (``CopStrategy``, heuristics.py) proved no
weaker than the experimental belief strategy in the strategy sprint, so
adaptation here only ever nudges *that* class's own two fields -- it never
swaps in a different strategy class. Its bound and learning rate are
deliberately the smallest in this module ("especially conservative" per the
sprint brief).
"""

from __future__ import annotations

from dataclasses import replace

from police_thief.learning.profile import LearningProfile
from police_thief.strategy.weights import ThiefWeights

LEARNING_RATE_THIEF = 0.4
LEARNING_RATE_COP = 0.2  # smaller: the cop side must stay especially conservative

# (min, max) per adapted field -- never crossed regardless of confidence.
THIEF_BOUNDS = {
    "barrier_confinement": (0.6, 2.4),
    "threat_distance": (1.0, 4.0),
}
COP_BARRIER_CONFIDENCE_BOUNDS = (0.10, 0.20)

_REFERENCE_MATCH_LENGTH = 35.0  # Appendix F max_moves default; see weights.py
# for why strategy-tuning code is allowed a plain constant here rather than
# reading config -- this is a rough behavioural reference, not game physics.


def _blend(baseline: float, target: float, confidence: float, rate: float, bounds) -> float:
    step = max(0.0, min(1.0, confidence)) * rate
    value = baseline + step * (target - baseline)
    lo, hi = bounds
    return max(lo, min(hi, value))


def _select_profile(
    global_profile: LearningProfile, opponent_profile: LearningProfile | None
) -> tuple[LearningProfile, float]:
    """Known opponent -> blend of opponent + global confidence, opponent
    stats dominating; unknown opponent -> global profile alone."""
    if opponent_profile is not None and opponent_profile.sample_count > 0:
        confidence = 0.7 * opponent_profile.confidence() + 0.3 * global_profile.confidence()
        return opponent_profile, confidence
    return global_profile, global_profile.confidence()


def derive_thief_weights(
    baseline: ThiefWeights,
    global_profile: LearningProfile,
    opponent_profile: LearningProfile | None,
) -> ThiefWeights:
    """A bounded ``ThiefWeights`` candidate for :class:`RiskThiefStrategy`."""
    profile, confidence = _select_profile(global_profile, opponent_profile)

    bc_lo, bc_hi = THIEF_BOUNDS["barrier_confinement"]
    barrier_target = bc_lo + profile.barrier_rate * (bc_hi - bc_lo)
    new_barrier_confinement = _blend(
        baseline.barrier_confinement, barrier_target, confidence,
        LEARNING_RATE_THIEF, THIEF_BOUNDS["barrier_confinement"],
    )

    td_lo, td_hi = THIEF_BOUNDS["threat_distance"]
    aggressiveness = max(0.0, min(1.0, 1.0 - profile.avg_turns / _REFERENCE_MATCH_LENGTH))
    threat_target = td_lo + aggressiveness * (td_hi - td_lo)
    new_threat_distance = _blend(
        baseline.threat_distance, threat_target, confidence,
        LEARNING_RATE_THIEF, THIEF_BOUNDS["threat_distance"],
    )

    return replace(
        baseline,
        barrier_confinement=new_barrier_confinement,
        threat_distance=new_threat_distance,
    )


def derive_cop_barrier_confidence(
    baseline_barrier_confidence: float,
    global_profile: LearningProfile,
    opponent_profile: LearningProfile | None,
) -> float:
    """A bounded ``barrier_confidence`` candidate for the production
    ``CopStrategy`` -- the only field this module adapts for the cop."""
    profile, confidence = _select_profile(global_profile, opponent_profile)
    predictability = max(profile.direction_bias.values(), default=0.0)
    lo, hi = COP_BARRIER_CONFIDENCE_BOUNDS
    # More predictable opponent -> commit to a barrier slightly sooner (lean
    # toward the lower bound); unpredictable -> stay at/near the baseline.
    target = hi - predictability * (hi - lo)
    return _blend(
        baseline_barrier_confidence, target, confidence,
        LEARNING_RATE_COP, COP_BARRIER_CONFIDENCE_BOUNDS,
    )
