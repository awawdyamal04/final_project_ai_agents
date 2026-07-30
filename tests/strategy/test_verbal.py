"""The verbal layer: composition, validation, interpretation, trust."""

from __future__ import annotations

import inspect

import pytest

from police_thief.config.loader import build_shared_config, load_shared_config
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role
from police_thief.strategy.tracker import OpponentTracker
from police_thief.strategy.verbal import (
    HintRejected,
    HintRequest,
    SafeHintProvider,
    TemplateHintProvider,
    default_provider,
    validate_hint,
)
from tests.conftest import SHARED_CONFIG_PATH


@pytest.fixture
def cfg():
    return load_shared_config(SHARED_CONFIG_PATH)


def request_for(turn=1, direction=Direction.N, area="New York", words=15):
    return HintRequest(
        game_id="g1", role="police", turn=turn,
        actual_direction=direction, map_area=area, max_words=words,
    )


# ----------------------------------------------------------------------
# Composition
# ----------------------------------------------------------------------


def test_truthful_hint_names_the_direction_actually_taken():
    provider = TemplateHintProvider(lie_every=0)   # never lie
    result = provider.compose(request_for(direction=Direction.E))
    assert result.intent == "truth"
    assert result.claimed_direction is Direction.E
    assert provider.interpret(result.text).claimed_direction is Direction.E


def test_misleading_hint_names_a_different_direction():
    """Assert what the hint *conveys*, not one spelling of it.

    The composer may pick a synonym -- "downtown" for south -- so pinning a
    literal word would be testing the phrasing table rather than the deception.
    """
    provider = TemplateHintProvider(lie_every=1)   # always lie
    result = provider.compose(request_for(direction=Direction.N))

    assert result.intent == "lie"
    assert result.claimed_direction is Direction.S
    assert provider.interpret(result.text).claimed_direction is Direction.S


def test_intent_is_always_declared_and_valid(cfg):
    provider = default_provider()
    for turn in range(1, 40):
        for direction in Direction:
            result = provider.compose(request_for(turn, direction))
            assert result.intent in ("truth", "lie")


def test_declared_intent_matches_what_was_claimed():
    """A lie must actually mislead, and a truth must actually be true."""
    provider = TemplateHintProvider()
    for turn in range(1, 60):
        for actual in (Direction.N, Direction.S, Direction.E, Direction.W):
            r = provider.compose(request_for(turn, actual))
            if r.intent == "truth":
                assert r.claimed_direction is actual
            else:
                assert r.claimed_direction is not actual


def test_hints_are_deterministic():
    """A replay must reproduce every hint exactly."""
    provider = TemplateHintProvider()
    first = provider.compose(request_for(7, Direction.W))
    for _ in range(20):
        assert provider.compose(request_for(7, Direction.W)) == first


def test_different_turns_give_different_phrasing():
    provider = TemplateHintProvider()
    texts = {provider.compose(request_for(t, Direction.N)).text for t in range(1, 12)}
    assert len(texts) > 1


def test_map_area_supplies_real_landmarks():
    provider = TemplateHintProvider(lie_every=0)
    ny = provider.compose(request_for(area="New York")).text
    generic = provider.compose(request_for(area="")).text
    assert any(p in ny for p in ("Times Square", "Central Park", "Brooklyn Bridge", "Harlem"))
    assert not any(p in generic for p in ("Times Square", "Central Park"))


def test_barrier_and_stay_hints_are_truthful():
    """Nothing to mislead about: the placement is publicly declared anyway."""
    provider = TemplateHintProvider(lie_every=1)
    assert provider.compose(request_for(direction=None)).intent == "truth"
    assert provider.compose(request_for(direction=Direction.STAY)).intent == "truth"


def test_every_generated_hint_passes_validation(cfg):
    provider = default_provider()
    limit = cfg.world.hint_max_words
    for turn in range(1, 80):
        for direction in list(Direction) + [None]:
            text = provider.compose(request_for(turn, direction, words=limit)).text
            validate_hint(text, limit)   # raises if illegal


def test_word_limit_comes_from_config_and_is_respected(cfg, valid_shared):
    valid_shared["world"]["hint_max_words"] = 3
    tight = build_shared_config(valid_shared)
    provider = default_provider()
    text = provider.compose(
        request_for(words=tight.world.hint_max_words)
    ).text
    assert len(text.split()) <= 3


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def test_overlong_hint_is_rejected():
    with pytest.raises(HintRejected, match="over the agreed limit"):
        validate_hint("word " * 20, 15)


def test_empty_hint_is_rejected():
    with pytest.raises(HintRejected, match="must not be empty"):
        validate_hint("   ", 15)


@pytest.mark.parametrize(
    "text",
    ["I am at (3,4)", "moving to [2,5]", "row=3 col=4", "heading 3,4", "now at B4"],
)
def test_numeric_position_protocols_are_rejected(text):
    """Forbidden: a coordinate protocol would bypass the verbal game."""
    with pytest.raises(HintRejected, match="numeric position"):
        validate_hint(text, 15)


def test_ordinary_prose_with_no_coordinates_is_accepted():
    validate_hint("slipping north past Times Square", 15)


# ----------------------------------------------------------------------
# Interpretation
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("heading north past the park", Direction.N),
        ("moving southward now", Direction.S),
        ("cutting east by the bridge", Direction.E),
        ("gone west side", Direction.W),
        ("holding still by the yard", Direction.STAY),
    ],
)
def test_interpretation_reads_the_claimed_direction(text, expected):
    reading = TemplateHintProvider().interpret(text)
    assert reading.claimed_direction is expected
    assert reading.confidence > 0.5


def test_interpretation_is_deterministic():
    provider = TemplateHintProvider()
    first = provider.interpret("slipping east past Harlem")
    for _ in range(10):
        assert provider.interpret("slipping east past Harlem") == first


def test_hint_with_no_direction_yields_no_claim():
    reading = TemplateHintProvider().interpret("you will never find me")
    assert reading.claimed_direction is None
    assert reading.confidence == 0.0


def test_contradictory_hint_is_treated_as_unclear():
    reading = TemplateHintProvider().interpret("north then south, who knows")
    assert reading.claimed_direction is None
    assert reading.confidence < 0.5


def test_round_trip_composition_and_interpretation():
    provider = TemplateHintProvider()
    for turn in range(1, 30):
        for direction in (Direction.N, Direction.S, Direction.E, Direction.W):
            result = provider.compose(request_for(turn, direction))
            reading = provider.interpret(result.text)
            assert reading.claimed_direction is result.claimed_direction


# ----------------------------------------------------------------------
# Safety
# ----------------------------------------------------------------------


class _Broken:
    name = "broken"

    def compose(self, request):
        raise RuntimeError("provider exploded")

    def interpret(self, text):
        raise RuntimeError("provider exploded")


class _Invalid:
    name = "invalid"

    def compose(self, request):
        from police_thief.strategy.verbal import HintResult

        return HintResult("I am at (3,4) " + "x " * 40, "nonsense", None, "invalid")

    def interpret(self, text):
        raise RuntimeError("boom")


def test_a_failing_provider_still_yields_a_usable_hint():
    """A hint decorates a move that is already decided; it must not fail a turn."""
    safe = SafeHintProvider(_Broken())
    result = safe.compose(request_for())
    assert result.text
    assert result.intent == "truth"
    assert "fallback" in result.provider
    assert safe.failures == 1


def test_an_invalid_provider_output_is_replaced_by_the_fallback():
    safe = SafeHintProvider(_Invalid())
    result = safe.compose(request_for(words=15))
    validate_hint(result.text, 15)
    assert "fallback" in result.provider


def test_a_failing_interpreter_degrades_to_no_claim():
    reading = SafeHintProvider(_Broken()).interpret("heading north")
    assert reading.claimed_direction is None
    assert reading.confidence == 0.0


def test_default_provider_is_offline_and_deterministic():
    provider = default_provider()
    assert provider.name == "template"
    first = provider.compose(request_for(3, Direction.S))
    assert provider.compose(request_for(3, Direction.S)) == first


# ----------------------------------------------------------------------
# Belief-confidence adjustment
# ----------------------------------------------------------------------


def tracker_for(cfg):
    return OpponentTracker(Role.POLICE, cfg, Board.from_config(cfg))


def test_trust_starts_at_even_odds(cfg):
    assert tracker_for(cfg).hint_reliability == 0.5


def test_a_corroborated_hint_earns_trust(cfg):
    t = tracker_for(cfg)
    t.opponent_scent.emit(Coordinate(2, 3))   # trail to the north
    before = t.hint_reliability
    t.note_hint(
        TemplateHintProvider().interpret("heading north"),
        own_cell=Coordinate(0, 0),
    )
    assert t.hint_reliability > before
    assert t.hints_seen == 1


def test_a_hint_contradicted_by_scent_costs_trust(cfg):
    """Chapter 4's worked example: the trail cannot be faked, so it wins."""
    t = tracker_for(cfg)
    for _ in range(4):
        t.opponent_scent.emit(Coordinate(6, 6))   # trail firmly south-east
    before = t.hint_reliability

    t.note_hint(
        TemplateHintProvider().interpret("heading north"),
        own_cell=Coordinate(0, 0),
    )
    assert t.hint_reliability < before
    assert t.hints_contradicted == 1


def test_a_persistent_liar_loses_all_influence(cfg):
    t = tracker_for(cfg)
    for _ in range(4):
        t.opponent_scent.emit(Coordinate(6, 6))
    for _ in range(6):
        t.note_hint(
            TemplateHintProvider().interpret("heading north"),
            own_cell=Coordinate(0, 0),
        )
    assert t.hint_reliability == 0.0


def test_hints_keep_the_belief_normalised(cfg):
    t = tracker_for(cfg)
    for text in ("heading north", "gone east", "moving south", "west side"):
        t.note_hint(
            TemplateHintProvider().interpret(text), own_cell=Coordinate(0, 0)
        )
        assert t.belief.is_normalised()


def test_an_unclear_hint_changes_nothing(cfg):
    t = tracker_for(cfg)
    before = dict(t.belief.probabilities)
    t.note_hint(
        TemplateHintProvider().interpret("you'll never catch me"),
        own_cell=Coordinate(0, 0),
    )
    assert t.belief.probabilities == before
    assert t.hints_seen == 0


# ----------------------------------------------------------------------
# Information boundary
# ----------------------------------------------------------------------


def test_the_request_carries_no_opponent_information():
    """A provider that wanted to leak has nothing to reach for."""
    import dataclasses

    names = {f.name for f in dataclasses.fields(HintRequest)}
    assert names == {
        "game_id", "role", "turn", "actual_direction", "map_area", "max_words"
    }
    for banned in (
        "opponent_position", "belief", "board", "state", "opponent_cell",
        "global_state", "harness",
    ):
        assert banned not in names


def test_the_verbal_layer_cannot_choose_or_validate_a_move():
    """It describes; it does not decide."""
    import police_thief.strategy.verbal as module

    source = inspect.getsource(module)
    for forbidden in (
        "legal_actions", "legal_moves", "validate_action", "validate_move",
        "apply_action", "calculate_score", "evaluate_capture",
    ):
        assert forbidden not in source


def test_the_verbal_layer_imports_no_game_logic():
    import ast
    from pathlib import Path

    tree = ast.parse(
        Path("src/police_thief/strategy/verbal.py").read_text(encoding="utf-8")
    )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)

    for forbidden in (
        "police_thief.domain.rules",
        "police_thief.domain.transition",
        "police_thief.domain.scoring",
        "police_thief.domain.capture",
        "police_thief.crypto.coordinator",
        "police_thief.sim.harness",
    ):
        assert forbidden not in imported
    # Only the direction enum is needed to talk about movement.
    assert "police_thief.domain.enums" in imported
