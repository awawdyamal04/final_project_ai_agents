"""Gatekeeper admission control and deadline/retry/watchdog behaviour.

All timing uses :class:`FakeClock`, so a suite exercising a 60-second watchdog
runs in microseconds and gives the same answer every time.
"""

from __future__ import annotations

import asyncio

import pytest

from police_thief.peer.clock import FakeClock
from police_thief.peer.deadline import DeadlineTracker, RetryPolicy, Watchdog
from police_thief.peer.gatekeeper import Gatekeeper, GatekeeperLimits
from police_thief.protocol.exceptions import (
    ConcurrencyLimitExceededError,
    PeerTimeoutError,
    PeerUnavailableError,
    ProtocolValidationError,
    QueueCapacityExceededError,
    RateLimitExceededError,
    RetryLimitExceededError,
)


# ----------------------------------------------------------------------
# Gatekeeper
# ----------------------------------------------------------------------


def limits(**overrides) -> GatekeeperLimits:
    base = {"requests_per_minute": 30, "concurrent_requests": 2, "queue_depth": 100}
    base.update(overrides)
    return GatekeeperLimits(**base)


def test_limits_come_from_shared_config(shared):
    built = GatekeeperLimits.from_config(shared)
    assert built.requests_per_minute == shared.rate_limiter_gatekeeper.requests_per_minute
    assert built.concurrent_requests == shared.rate_limiter_gatekeeper.concurrent_requests
    assert built.queue_depth == shared.rate_limiter_gatekeeper.queue_depth
    assert built.refill_per_second == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_request_below_the_threshold_is_admitted():
    gate = Gatekeeper(limits(), FakeClock())
    async with gate.slot():
        assert gate.in_flight == 1
    assert gate.in_flight == 0


@pytest.mark.asyncio
async def test_bucket_starts_full_so_a_startup_burst_succeeds():
    """A peer that has just started must be able to handshake immediately."""
    gate = Gatekeeper(limits(requests_per_minute=30), FakeClock())
    for _ in range(30):
        async with gate.slot():
            pass
    assert gate.available_tokens() < 1.0


@pytest.mark.asyncio
async def test_rate_limit_is_enforced_once_the_bucket_empties():
    gate = Gatekeeper(limits(requests_per_minute=3), FakeClock())
    for _ in range(3):
        async with gate.slot():
            pass
    with pytest.raises(RateLimitExceededError, match="rate limit reached"):
        async with gate.slot():
            pass
    assert gate.rejections == 1


@pytest.mark.asyncio
async def test_bucket_refills_over_time():
    clock = FakeClock()
    gate = Gatekeeper(limits(requests_per_minute=60), clock)
    for _ in range(60):
        async with gate.slot():
            pass
    with pytest.raises(RateLimitExceededError):
        async with gate.slot():
            pass

    clock.advance(1.0)  # 60/min == 1 token/second
    async with gate.slot():
        pass


@pytest.mark.asyncio
async def test_bucket_does_not_refill_above_capacity():
    clock = FakeClock()
    gate = Gatekeeper(limits(requests_per_minute=10), clock)
    clock.advance(3600)
    assert gate.available_tokens() == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_concurrency_limit_is_enforced():
    gate = Gatekeeper(limits(concurrent_requests=2), FakeClock())

    async def hold(barrier: asyncio.Event) -> None:
        async with gate.slot():
            await barrier.wait()

    barrier = asyncio.Event()
    a = asyncio.create_task(hold(barrier))
    b = asyncio.create_task(hold(barrier))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    with pytest.raises(ConcurrencyLimitExceededError, match="already in flight"):
        async with gate.slot():
            pass

    barrier.set()
    await asyncio.gather(a, b)
    assert gate.in_flight == 0


@pytest.mark.asyncio
async def test_queue_capacity_is_enforced_first():
    """Queue depth is the outermost gate: refuse work we could not get to."""
    gate = Gatekeeper(limits(queue_depth=1, concurrent_requests=5), FakeClock())

    async def hold(barrier: asyncio.Event) -> None:
        async with gate.slot():
            await barrier.wait()

    barrier = asyncio.Event()
    task = asyncio.create_task(hold(barrier))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    with pytest.raises(QueueCapacityExceededError, match="queue_depth"):
        async with gate.slot():
            pass

    barrier.set()
    await task


@pytest.mark.asyncio
async def test_slot_is_released_when_the_guarded_body_raises():
    """A leaked slot permanently reduces the peer's capacity."""
    gate = Gatekeeper(limits(), FakeClock())
    with pytest.raises(RuntimeError):
        async with gate.slot():
            raise RuntimeError("boom")
    assert gate.in_flight == 0
    async with gate.slot():
        pass


@pytest.mark.asyncio
async def test_admission_happens_before_the_body_runs():
    gate = Gatekeeper(limits(requests_per_minute=1), FakeClock())
    async with gate.slot():
        pass

    ran = False
    with pytest.raises(RateLimitExceededError):
        async with gate.slot():
            ran = True  # pragma: no cover
    assert not ran


# ----------------------------------------------------------------------
# Deadline and retry
# ----------------------------------------------------------------------


def policy(**overrides) -> RetryPolicy:
    base = {"response_timeout_sec": 30, "max_retries": 3, "retry_backoff_sec": 5}
    base.update(overrides)
    return RetryPolicy(**base)


def test_retry_policy_comes_from_shared_config(shared):
    built = RetryPolicy.from_config(shared)
    assert built.response_timeout_sec == 30
    assert built.max_retries == 3
    assert built.retry_backoff_sec == 5
    assert built.max_attempts == 4


@pytest.mark.asyncio
async def test_success_on_the_first_attempt():
    tracker = DeadlineTracker(policy(), FakeClock())

    async def op() -> str:
        return "ok"

    assert await tracker.run(op) == "ok"
    assert len(tracker.attempts) == 1


@pytest.mark.asyncio
async def test_transient_failure_then_success():
    clock = FakeClock()
    tracker = DeadlineTracker(policy(), clock)
    calls = {"n": 0}

    async def op() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise PeerUnavailableError("not yet")
        return "ok"

    assert await tracker.run(op) == "ok"
    assert calls["n"] == 3
    assert clock.sleeps == [5.0, 5.0]  # backoff between attempts


@pytest.mark.asyncio
async def test_retry_limit_is_reached_and_never_exceeded():
    clock = FakeClock()
    tracker = DeadlineTracker(policy(max_retries=2), clock)
    calls = {"n": 0}

    async def op() -> str:
        calls["n"] += 1
        raise PeerUnavailableError("always down")

    with pytest.raises(RetryLimitExceededError, match="after 3 attempts"):
        await tracker.run(op)
    assert calls["n"] == 3  # 1 initial + 2 retries, never more


@pytest.mark.asyncio
async def test_non_retryable_error_is_not_retried():
    """Resending a malformed message produces the same rejection and spends
    the rate budget the Gatekeeper exists to protect."""
    tracker = DeadlineTracker(policy(), FakeClock())
    calls = {"n": 0}

    async def op() -> str:
        calls["n"] += 1
        raise ProtocolValidationError("schema violation")

    with pytest.raises(ProtocolValidationError):
        await tracker.run(op)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_timeout_becomes_a_peer_timeout_error():
    tracker = DeadlineTracker(policy(response_timeout_sec=0), FakeClock())

    async def op() -> str:
        await asyncio.sleep(10)
        return "never"  # pragma: no cover

    with pytest.raises((PeerTimeoutError, RetryLimitExceededError)):
        await tracker.run(op)


@pytest.mark.asyncio
async def test_cancellation_propagates_without_retrying():
    tracker = DeadlineTracker(policy(), FakeClock())

    async def op() -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await tracker.run(op)


# ----------------------------------------------------------------------
# Watchdog
# ----------------------------------------------------------------------


def test_watchdog_stays_quiet_while_the_heartbeat_continues():
    clock = FakeClock()
    fired: list[float] = []
    dog = Watchdog(60, fired.append, clock)

    for _ in range(10):
        clock.advance(30)
        dog.heartbeat()
        assert not dog.check()
    assert fired == []


def test_watchdog_fires_after_the_configured_silence():
    clock = FakeClock()
    fired: list[float] = []
    dog = Watchdog(60, fired.append, clock)

    clock.advance(59)
    assert not dog.check()
    clock.advance(1)
    assert dog.check()
    assert fired == [60.0]
    assert dog.fired


def test_watchdog_fires_only_once():
    """A watchdog that fires repeatedly turns one failure into a storm."""
    clock = FakeClock()
    fired: list[float] = []
    dog = Watchdog(10, fired.append, clock)

    clock.advance(100)
    assert dog.check()
    clock.advance(100)
    assert not dog.check()
    assert len(fired) == 1


def test_watchdog_timeout_comes_from_shared_config(shared):
    assert shared.network_and_league.watchdog_timeout_sec == 60
    clock = FakeClock()
    dog = Watchdog(shared.network_and_league.watchdog_timeout_sec, lambda _: None, clock)
    clock.advance(59.9)
    assert not dog.check()
    clock.advance(0.2)
    assert dog.check()


def test_response_timeout_is_shorter_than_the_watchdog(shared):
    """Otherwise the watchdog fires before a request can time out, and the two
    mechanisms collapse into one."""
    assert (
        shared.network_and_league.response_timeout_sec
        < shared.network_and_league.watchdog_timeout_sec
    )


@pytest.mark.asyncio
async def test_watchdog_stop_is_cancellation_safe():
    dog = Watchdog(60, lambda _: None, FakeClock())
    dog.start(interval=0.01)
    await asyncio.sleep(0)
    await dog.stop()
    await dog.stop()  # idempotent
