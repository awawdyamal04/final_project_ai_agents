"""Deadline tracking, bounded retry, and the watchdog (E-6, E-7).

Two distinct responsibilities the PDF is careful to separate (Ch. 8, PDF p. 81):

* the **deadline tracker** guards *one request* -- ``response_timeout_sec``;
* the **watchdog** guards *the whole process* -- ``watchdog_timeout_sec``.

And the rule that governs both: *"a request whose expiry has passed **must** be
treated as a failure -- not as an invitation to wait longer"* (PDF p. 81).
Leaving a request hanging with no expiry is the direct recipe for a deadlock.

Retries are bounded by ``max_retries`` and spaced by ``retry_backoff_sec``, both
from configuration. Nothing here retries forever, and nothing here retries a
validation failure -- resending a malformed message produces the same rejection
and spends the rate budget the Gatekeeper exists to protect.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from police_thief.config.models import SharedConfig
from police_thief.peer.clock import Clock, SystemClock
from police_thief.protocol.exceptions import (
    PeerProtocolError,
    PeerTimeoutError,
    RetryLimitExceededError,
    TransportError,
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry parameters, from the shared configuration."""

    response_timeout_sec: int
    max_retries: int
    retry_backoff_sec: int

    @classmethod
    def from_config(cls, config: SharedConfig) -> RetryPolicy:
        return cls(
            response_timeout_sec=config.network_and_league.response_timeout_sec,
            max_retries=config.rate_limiter_gatekeeper.max_retries,
            retry_backoff_sec=config.rate_limiter_gatekeeper.retry_backoff_sec,
        )

    @property
    def max_attempts(self) -> int:
        """One initial attempt plus ``max_retries`` retries."""
        return self.max_retries + 1


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """What happened on one attempt, for the operational log."""

    attempt: int
    error: str | None
    elapsed: float


class DeadlineTracker:
    """Runs an awaitable under a deadline, with bounded retries."""

    def __init__(self, policy: RetryPolicy, clock: Clock | None = None) -> None:
        self._policy = policy
        self._clock = clock or SystemClock()
        self.attempts: list[AttemptRecord] = []

    @property
    def policy(self) -> RetryPolicy:
        return self._policy

    async def run(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        description: str = "request",
    ) -> T:
        """Attempt ``operation`` until it succeeds or the bounds are reached.

        Retries only :class:`TransportError` subclasses whose ``retryable`` flag
        is set. A protocol validation failure propagates on the first attempt,
        unretried.
        """
        self.attempts.clear()
        last_error: BaseException | None = None

        for attempt in range(1, self._policy.max_attempts + 1):
            started = self._clock.monotonic()
            try:
                result = await self._with_deadline(operation())
            except asyncio.CancelledError:
                # Cancellation is not a failure to retry. Propagate promptly so
                # shutdown stays responsive.
                raise
            except PeerProtocolError as exc:
                elapsed = self._clock.monotonic() - started
                self.attempts.append(
                    AttemptRecord(attempt, type(exc).__name__, elapsed)
                )
                if not exc.retryable:
                    raise
                last_error = exc
            except Exception as exc:  # transport libraries raise their own types
                elapsed = self._clock.monotonic() - started
                self.attempts.append(
                    AttemptRecord(attempt, type(exc).__name__, elapsed)
                )
                last_error = exc
            else:
                elapsed = self._clock.monotonic() - started
                self.attempts.append(AttemptRecord(attempt, None, elapsed))
                return result

            if attempt < self._policy.max_attempts:
                await self._clock.sleep(float(self._policy.retry_backoff_sec))

        raise RetryLimitExceededError(
            f"{description} failed after {self._policy.max_attempts} attempts "
            f"({self._policy.max_retries} retries, "
            f"{self._policy.retry_backoff_sec}s backoff); "
            f"last error: {type(last_error).__name__}: {last_error}"
        ) from last_error

    async def _with_deadline(self, awaitable: Awaitable[T]) -> T:
        """Enforce ``response_timeout_sec`` on a single attempt."""
        try:
            return await asyncio.wait_for(
                awaitable, timeout=float(self._policy.response_timeout_sec)
            )
        except asyncio.TimeoutError as exc:
            raise PeerTimeoutError(
                f"no response within {self._policy.response_timeout_sec}s; "
                f"a missed deadline is a failure, not a reason to wait longer"
            ) from exc


class Watchdog:
    """Monitors the peer's heartbeat and fires once if it stops (E-7).

    Guards the whole process, not one request. Ch. 8 (PDF p. 81): an
    independent monitor that, on detecting a freeze, performs a controlled
    shutdown and persists state, rather than letting the match die silently.

    Fires **once**. A watchdog that fires repeatedly turns one failure into a
    storm of shutdown attempts.
    """

    def __init__(
        self,
        timeout_sec: float,
        on_stall: Callable[[float], None],
        clock: Clock | None = None,
    ) -> None:
        self._timeout = float(timeout_sec)
        self._on_stall = on_stall
        self._clock = clock or SystemClock()
        self._last_beat = self._clock.monotonic()
        self._fired = False
        self._task: asyncio.Task[None] | None = None

    @property
    def fired(self) -> bool:
        return self._fired

    def heartbeat(self) -> None:
        self._last_beat = self._clock.monotonic()

    def silence(self) -> float:
        return self._clock.monotonic() - self._last_beat

    def check(self) -> bool:
        """Evaluate once. Returns ``True`` if the stall handler ran."""
        if self._fired:
            return False
        if self.silence() >= self._timeout:
            self._fired = True
            self._on_stall(self.silence())
            return True
        return False

    async def _loop(self, interval: float) -> None:
        try:
            while not self._fired:
                await self._clock.sleep(interval)
                self.check()
        except asyncio.CancelledError:
            # Cancellation-safe: stopping the watchdog is a normal shutdown
            # step, not an error.
            raise

    def start(self, interval: float = 1.0) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(interval))

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
