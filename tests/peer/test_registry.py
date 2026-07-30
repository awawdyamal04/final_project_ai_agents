"""Message registry: idempotency, conflict detection, bounded memory."""

from __future__ import annotations

import pytest

from police_thief.peer.registry import MessageRegistry
from police_thief.protocol.exceptions import ConflictingDuplicateError


def test_unseen_message_is_a_miss():
    assert MessageRegistry(10).lookup("m1", {"a": 1}) is None


def test_exact_duplicate_returns_the_cached_response():
    """A retry after a lost response must not redo the work."""
    registry = MessageRegistry(10)
    registry.record("m1", {"a": 1}, {"ok": True, "n": 42})

    hit = registry.lookup("m1", {"a": 1})
    assert hit is not None
    assert hit.response == {"ok": True, "n": 42}


def test_duplicate_detection_ignores_key_order():
    """Two payloads differing only in key order are the same message.

    An opponent whose JSON library orders keys differently from ours would
    otherwise have every retry rejected as a conflict.
    """
    registry = MessageRegistry(10)
    registry.record("m1", {"a": 1, "b": 2}, {"ok": True})
    assert registry.lookup("m1", {"b": 2, "a": 1}) is not None


def test_conflicting_reuse_is_rejected():
    """Reusing an id with a different payload is an attempt to change a
    decision after the fact -- what commit-reveal exists to prevent."""
    registry = MessageRegistry(10)
    registry.record("m1", {"a": 1}, {"ok": True})
    with pytest.raises(ConflictingDuplicateError, match="different payload"):
        registry.lookup("m1", {"a": 2})


def test_registry_is_bounded_and_evicts_oldest_first():
    registry = MessageRegistry(3)
    for i in range(5):
        registry.record(f"m{i}", {"i": i}, {"ok": True})

    assert len(registry) == 3
    assert registry.evictions == 2
    assert "m0" not in registry and "m1" not in registry
    assert "m2" in registry and "m4" in registry


def test_evicted_id_is_treated_as_new():
    """A stale id past the bound is a miss, not a conflict. The alternative --
    remembering forever -- is a memory leak a long series would find."""
    registry = MessageRegistry(2)
    registry.record("old", {"a": 1}, {"ok": True})
    registry.record("m1", {"a": 1}, {"ok": True})
    registry.record("m2", {"a": 1}, {"ok": True})

    assert "old" not in registry
    assert registry.lookup("old", {"a": 999}) is None


def test_recording_again_refreshes_recency():
    registry = MessageRegistry(2)
    registry.record("a", {"x": 1}, {"ok": True})
    registry.record("b", {"x": 2}, {"ok": True})
    registry.record("a", {"x": 1}, {"ok": True})  # refresh a
    registry.record("c", {"x": 3}, {"ok": True})  # evicts b

    assert "a" in registry and "c" in registry
    assert "b" not in registry


def test_capacity_must_be_positive():
    with pytest.raises(ValueError, match="at least 1"):
        MessageRegistry(0)


def test_capacity_comes_from_queue_depth(shared):
    registry = MessageRegistry(shared.rate_limiter_gatekeeper.queue_depth)
    assert registry.capacity == 100


def test_memory_stays_bounded_under_sustained_load():
    registry = MessageRegistry(50)
    for i in range(10_000):
        registry.record(f"m{i}", {"i": i}, {"ok": True})
    assert len(registry) == 50


def test_clear_empties_the_registry():
    registry = MessageRegistry(5)
    registry.record("m1", {"a": 1}, {"ok": True})
    registry.clear()
    assert len(registry) == 0
