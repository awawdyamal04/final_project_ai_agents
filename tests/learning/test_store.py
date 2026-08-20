"""Persistence: creation, reload, per-opponent keying, corrupt-file safety."""

from __future__ import annotations

from police_thief.learning import store
from police_thief.learning.profile import LearningProfile


def _fresh_observation() -> LearningProfile:
    profile = LearningProfile()
    profile.update(
        direction_bias={"N": 0.4, "S": 0.1, "E": 0.3, "W": 0.2},
        barrier_rate=0.5,
        turns_played=28,
        was_technical_loss=False,
    )
    return profile


def test_profile_created_after_a_valid_completed_match(learning_dir):
    profile = _fresh_observation()
    store.save_global_profile(profile, learning_dir)
    path = store._global_path(learning_dir)
    assert path.exists()


def test_profile_reload_on_next_match(learning_dir):
    profile = _fresh_observation()
    store.save_global_profile(profile, learning_dir)

    reloaded = store.load_global_profile(learning_dir)
    assert reloaded.games_seen == 1
    assert reloaded.sample_count == 1
    assert reloaded.barrier_rate == profile.barrier_rate


def test_same_group_id_reuses_opponent_profile(learning_dir):
    key = store.opponent_key("Team B")
    profile = _fresh_observation()
    store.save_opponent_profile(key, profile, learning_dir)

    same_key_again = store.opponent_key("Team B")
    assert same_key_again == key
    reloaded = store.load_opponent_profile(same_key_again, learning_dir)
    assert reloaded.games_seen == 1


def test_unknown_group_id_falls_back_to_a_stable_unknown_key():
    assert store.opponent_key(None) == "unknown"
    assert store.opponent_key("") == "unknown"
    assert store.opponent_key("   ") == "unknown"


def test_missing_profile_file_yields_a_fresh_default_profile(learning_dir):
    profile = store.load_opponent_profile("never-seen-before", learning_dir)
    assert profile.games_seen == 0
    assert profile.sample_count == 0
    assert profile.confidence() == 0.0


def test_corrupt_profile_fails_safely(learning_dir):
    path = store._global_path(learning_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json at all", encoding="utf-8")

    profile = store.load_global_profile(learning_dir)  # must not raise
    assert profile.games_seen == 0
    assert profile.confidence() == 0.0


def test_profile_with_wrong_json_shape_fails_safely(learning_dir):
    path = store._global_path(learning_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")  # valid JSON, wrong shape

    profile = store.load_global_profile(learning_dir)  # must not raise
    assert profile.games_seen == 0
