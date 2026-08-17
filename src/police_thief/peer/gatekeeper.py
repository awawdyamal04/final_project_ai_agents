"""The Gatekeeper: admission control on outbound requests (E-28, E-29).

Three cumulative gates in a fixed order, failing as early as possible:

1. **Queue capacity** -- ``queue_depth``. Refuses work we could not get to.
2. **Rate** -- ``requests_per_minute``, as a token bucket. Ch. 9 (PDF p. 90)
   gives the rule: ``tokens <- min(C, tokens + r*dt)``, allow iff
   ``tokens >= 1``.
3. **Concurrency** -- ``concurrent_requests``. Caps simultaneous in-flight work.

All three limits come from :class:`SharedConfig`; no Appendix F literal appears
here.

Built now for peer-to-peer traffic and deliberately reusable, because Phase 9
needs exactly this in front of the Gmail API, where the cost of getting it wrong
is a 429 and a suspended account (Ch. 9, PDF p. 95). The quota manager and
denial-of-service detector that complete the pattern belong to that phase; this
is the shared core.

A slot is always released, including when the guarded call raises -- a leaked
slot is a peer that stops sending after N failures and never recovers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from police_thief.config.models import SharedConfig
from police_thief.peer.clock import Clock, SystemClock
from police_thief.protocol.exceptions import (
    ConcurrencyLimitExceededError,
    QueueCapacityExceededError,
    RateLimitExceededError,
)


@dataclass(frozen=True, slots=True)
class GatekeeperLimits:
    """Limits, read from the shared configuration."""

    requests_per_minute: int
    concurrent_requests: int
    queue_depth: int

    @classmethod
    def from_config(cls, config: SharedConfig) -> GatekeeperLimits:
        limiter = config.rate_limiter_gatekeeper
        return cls(
            requests_per_minute=limiter.requests_per_minute,
            concurrent_requests=limiter.concurrent_requests,
            queue_depth=limiter.queue_depth,
        )

    @property
    def refill_per_second(self) -> float:
        return self.requests_per_minute / 60.0


class Gatekeeper:
    """Token-bucket rate limiting with bounded concurrency and queueing."""

    def __init__(
        self,
        limits: GatekeeperLimits,
        clock: Clock | None = None,
    ) -> None:
        self._limits = limits
        self._clock = clock or SystemClock()
        # Bucket starts full: a peer that has just started should be able to
        # send its handshake burst without waiting a minute for tokens.
        self._tokens = float(limits.requests_per_minute)
        self._last_refill = self._clock.monotonic()
        self._in_flight = 0
        self._queued = 0
        self.rejections = 0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def limits(self) -> GatekeeperLimits:
        return self._limits

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def queued(self) -> int:
        return self._queued

    def available_tokens(self) -> float:
        self._refill()
        return self._tokens

    # ------------------------------------------------------------------
    # Token bucket
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        now = self._clock.monotonic()
        elapsed = max(0.0, now - self._last_refill)
        capacity = float(self._limits.requests_per_minute)
        self._tokens = min(capacity, self._tokens + elapsed * self._limits.refill_per_second)
        self._last_refill = now

    # ------------------------------------------------------------------
    # Admission
    # ------------------------------------------------------------------

    def _admit(self) -> None:
        """Apply all three gates. Raises on the first that refuses.

        The capacity check counts requests *already* queued or in flight, not
        the one being admitted. Counting itself would make ``queue_depth=1``
        reject everything, which is a limit of one meaning a limit of none.
        """
        outstanding = self._queued + self._in_flight
        if outstanding >= self._limits.queue_depth:
            self.rejections += 1
            raise QueueCapacityExceededError(
                f"{outstanding} requests queued or in flight, at the "
                f"queue_depth limit of {self._limits.queue_depth}"
            )

        self._refill()
        if self._tokens < 1.0:
            self.rejections += 1
            raise RateLimitExceededError(
                f"rate limit reached: {self._limits.requests_per_minute} "
                f"requests per minute; "
                f"{self._tokens:.3f} tokens available"
            )

        if self._in_flight >= self._limits.concurrent_requests:
            self.rejections += 1
            raise ConcurrencyLimitExceededError(
                f"{self._in_flight} requests already in flight, at the "
                f"concurrent_requests limit of "
                f"{self._limits.concurrent_requests}"
            )

        self._tokens -= 1.0
        self._in_flight += 1

    def _release(self) -> None:
        self._in_flight = max(0, self._in_flight - 1)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire a slot for one outbound request.

        Raises before the guarded body runs if any gate refuses -- the whole
        point of admission control is that it happens *before* expensive
        processing.
        """
        self._admit()
        try:
            yield
        finally:
            # Released on every path, including exceptions. A leaked slot would
            # permanently reduce the peer's capacity.
            self._release()
