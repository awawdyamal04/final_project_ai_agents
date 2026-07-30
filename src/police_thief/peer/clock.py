"""Injectable clocks.

Every timeout, rate window and backoff in this package reads time through a
:class:`Clock`. Tests inject :class:`FakeClock` and advance it explicitly, so a
suite that exercises a 60-second watchdog runs in microseconds and gives the
same answer every time. A test that waits for real time is a test that is slow
*and* flaky.
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    """Monotonic time plus the ability to wait."""

    def monotonic(self) -> float:
        """Seconds from an arbitrary origin. Never goes backwards.

        Monotonic rather than wall-clock deliberately: Ch. 11 (PDF p. 109)
        names a drifting local clock among the real-world failures the system
        must survive, and an NTP correction mid-match must not make a deadline
        fire early or never.
        """
        ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """Real time."""

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeClock:
    """Manually advanced time, for tests.

    ``sleep`` advances the clock instead of waiting, so code under test
    experiences the passage of time without any elapsing.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("a monotonic clock cannot move backwards")
        self._now += seconds

    async def sleep(self, seconds: float) -> None:
        """Advance virtual time, and yield to the event loop.

        The yield matters as much as the advance. Without it, a coroutine
        waiting on a fake clock spins without ever letting its counterpart run,
        so two peers driven concurrently deadlock in the test even though the
        real thing works. ``asyncio.sleep(0)`` reschedules without consuming
        real time.
        """
        self.sleeps.append(seconds)
        self.advance(seconds)
        await asyncio.sleep(0)
