"""The explicit code-level boundary: nothing in ``learning`` may import
global/omniscient truth (``police_thief.replay`` or ``police_thief.sim``),
and the feature extractor only ever sees an OpponentModel plus this peer's
own honest bookkeeping -- never an opponent coordinate.
"""

from __future__ import annotations

import ast
from pathlib import Path

from police_thief.domain.enums import Direction, Role
from police_thief.learning.features import extract_observation
from police_thief.strategy.opponent_model import OpponentModel

FORBIDDEN_MODULES = ("police_thief.replay", "police_thief.sim")
LEARNING_SRC = Path(__file__).resolve().parents[2] / "src" / "police_thief" / "learning"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_learning_module_imports_replay_or_sim_truth():
    py_files = list(LEARNING_SRC.glob("*.py"))
    assert py_files, "expected learning package files to exist"
    for path in py_files:
        imported = _imported_modules(path)
        for forbidden in FORBIDDEN_MODULES:
            offenders = {name for name in imported if name.startswith(forbidden)}
            assert not offenders, f"{path.name} imports forbidden {offenders}"


def test_extract_observation_only_uses_legal_aggregate_fields():
    """The observation is built entirely from an OpponentModel's own public
    (already-legal) aggregates and this peer's own turn count/exit status --
    nothing resembling a coordinate is accepted or produced."""
    model = OpponentModel()
    # Feed it exactly what a real strategy would observe: a LocalView is not
    # constructed here (out of scope for this boundary check), but the model
    # itself never exposes anything beyond direction_bias()/barrier_rate().
    observation = extract_observation(
        role=Role.THIEF,
        opponent_key="team-b",
        opponent_model=model,
        turns_played=12,
        exit_status="MATCH COMPLETE",
    )
    allowed_fields = {
        "opponent_key", "direction_bias", "barrier_rate",
        "turns_played", "was_technical_loss", "trustworthy",
    }
    assert set(observation.__dataclass_fields__) == allowed_fields
    directions = {d.value for d in (Direction.N, Direction.S, Direction.E, Direction.W)}
    assert set(observation.direction_bias) == directions
    for value in observation.direction_bias.values():
        assert isinstance(value, float)


def test_trustworthy_flag_requires_clean_finish():
    model = OpponentModel()
    dirty = extract_observation(
        role=Role.THIEF,
        opponent_key="team-b",
        opponent_model=model,
        turns_played=3,
        exit_status="TECHNICAL LOSS",
    )
    assert dirty.trustworthy is False
    assert dirty.was_technical_loss is True

    clean = extract_observation(
        role=Role.THIEF,
        opponent_key="team-b",
        opponent_model=model,
        turns_played=30,
        exit_status="MATCH COMPLETE",
    )
    assert clean.trustworthy is True
    assert clean.was_technical_loss is False


def test_police_role_never_reports_a_barrier_rate():
    """barrier_rate is cop-exclusive ground truth (PDF p. 37): from the
    police peer's own model, board-barrier growth is its own placement, not
    an opponent tendency, so it must always read 0.0 -- regardless of what
    the underlying OpponentModel would otherwise compute."""
    model = OpponentModel(barrier_events=3.0, turns_observed=5)
    assert model.barrier_rate() > 0.0  # sanity: the model itself did observe growth

    observation = extract_observation(
        role=Role.POLICE,
        opponent_key="team-b",
        opponent_model=model,
        turns_played=10,
        exit_status="MATCH COMPLETE",
    )
    assert observation.barrier_rate == 0.0


def test_thief_role_passes_through_the_real_barrier_rate():
    """From the thief's own model, board-barrier growth is legitimately the
    cop's placement frequency, so it must pass through unchanged."""
    model = OpponentModel(barrier_events=3.0, turns_observed=5)
    expected = model.barrier_rate()
    assert expected > 0.0

    observation = extract_observation(
        role=Role.THIEF,
        opponent_key="team-b",
        opponent_model=model,
        turns_played=10,
        exit_status="MATCH COMPLETE",
    )
    assert observation.barrier_rate == expected
