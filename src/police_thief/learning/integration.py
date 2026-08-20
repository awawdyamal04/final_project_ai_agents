"""Wires the learning layer into one real match's before/after lifecycle.

Kept out of ``peer/orchestrator.py`` entirely -- the safest integration point
found in inspection is ``peer/run.py``, which already owns strategy
selection (it reads ``orchestrator.strategy`` after construction) and the
turn loop (``_play_turns``), so this module only ever hands ``run.py`` a
ready-made strategy object and two small hook functions. Nothing here
changes the protocol, the commit-reveal turn state machine, the audit chain,
or capture_claim.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from police_thief.domain.enums import Role
from police_thief.learning import adaptation
from police_thief.learning.features import extract_observation
from police_thief.learning.profile import LearningProfile
from police_thief.learning.store import (
    load_global_profile,
    load_opponent_profile,
    opponent_key,
    save_global_profile,
    save_opponent_profile,
)
from police_thief.strategy.base import BaseStrategy
from police_thief.strategy.heuristics import CopStrategy
from police_thief.strategy.opponent_model import OpponentModel
from police_thief.strategy.thief_risk import RiskThiefStrategy
from police_thief.strategy.weights import ThiefWeights


def prepare_adaptive_strategy(
    role: Role, learning_dir: Path, declared_opponent_name: str | None, seed: int | None
) -> tuple[BaseStrategy, OpponentModel, list[str]]:
    """A bounded, profile-informed strategy for this match, plus the model
    to keep observing through it and the status lines to print (no private
    or hidden information in them -- aggregate counts and floats only)."""
    key = opponent_key(declared_opponent_name)
    global_profile = load_global_profile(learning_dir)
    opponent_profile = load_opponent_profile(key, learning_dir) if key != "unknown" else None
    model = OpponentModel()

    lines = ["adaptive learning: enabled"]
    if opponent_profile is not None and opponent_profile.sample_count > 0:
        lines.append(f"opponent profile: {key} ({opponent_profile.games_seen} prior games)")
        _, confidence = _effective(global_profile, opponent_profile)
    else:
        lines.append(f"opponent profile: {key} (none yet -- using global profile)")
        _, confidence = _effective(global_profile, None)
    lines.append(f"global games learned: {global_profile.games_seen}")
    lines.append(f"adaptation confidence: {confidence:.2f}")

    if role is Role.POLICE:
        baseline = CopStrategy()
        barrier_confidence = adaptation.derive_cop_barrier_confidence(
            baseline.barrier_confidence, global_profile, opponent_profile
        )
        strategy: BaseStrategy = replace(baseline, barrier_confidence=barrier_confidence)
    else:
        weights = adaptation.derive_thief_weights(ThiefWeights(), global_profile, opponent_profile)
        strategy = RiskThiefStrategy(weights=weights, seed=seed, opponent_model=model)

    return strategy, model, lines


def _effective(
    global_profile: LearningProfile, opponent_profile: LearningProfile | None
) -> tuple[LearningProfile, float]:
    if opponent_profile is not None and opponent_profile.sample_count > 0:
        return opponent_profile, (
            0.7 * opponent_profile.confidence() + 0.3 * global_profile.confidence()
        )
    return global_profile, global_profile.confidence()


def record_match_outcome(
    *,
    role: Role,
    learning_dir: Path,
    declared_opponent_name: str | None,
    opponent_model: OpponentModel,
    turns_played: int,
    exit_status: str,
) -> str:
    """After-match hook. Returns the status line to print. Never raises --
    a learning-store problem must never surface as a match failure; any
    unexpected error here is swallowed into a "not saved" status instead.
    """
    try:
        key = opponent_key(declared_opponent_name)
        observation = extract_observation(
            role=role,
            opponent_key=key,
            opponent_model=opponent_model,
            turns_played=turns_played,
            exit_status=exit_status,
        )
        if not observation.trustworthy:
            return "learning update: skipped (match not clean enough to learn from)"

        global_profile = load_global_profile(learning_dir)
        global_profile.update(
            direction_bias=observation.direction_bias,
            barrier_rate=observation.barrier_rate,
            turns_played=observation.turns_played,
            was_technical_loss=observation.was_technical_loss,
        )
        save_global_profile(global_profile, learning_dir)

        opponent_profile = load_opponent_profile(key, learning_dir)
        opponent_profile.update(
            direction_bias=observation.direction_bias,
            barrier_rate=observation.barrier_rate,
            turns_played=observation.turns_played,
            was_technical_loss=observation.was_technical_loss,
        )
        save_opponent_profile(key, opponent_profile, learning_dir)
        return "learning update: saved"
    except Exception as exc:  # pragma: no cover - defensive, never fatal
        return f"learning update: not saved ({type(exc).__name__})"
