"""One sub-game's handshake within a series (split out of :mod:`series_v3`):
mirrors the kit's own ``netplay.handshake`` -- a bystander greeting (wrong
sub-game, or a role collision) does not abort the series, it is stashed
under its own declared round and the wait continues on the same budget.

**Why stash, not discard.** The kit's own ``handshake`` loop *discards* a
mismatched greeting (catches ``Refused`` for SPAR-N06/N07 and just polls
again) because in its shape the opponent re-greets fresh once we open the
next round's handshake ourselves. Observed live, a next-round greeting can
already be sitting in the queue -- the opponent settled its side first and
sent it before we finished settling ours -- and discarding it would strand
us waiting for a message that was already delivered once and will not be
resent. Stashing it under its own round costs nothing and closes that gap.
"""

from __future__ import annotations

import asyncio
from typing import Any

from police_thief.interop.exceptions import Refused
from police_thief.interop.negotiation import Agreed, Greeting, verify_greeting


async def negotiate_round(
    negotiate_q: asyncio.Queue,
    greeting: Greeting,
    *,
    sub_game_number: int,
    timeout: float,
    pending: dict[int, Any],
) -> Agreed:
    """Wait up to ``timeout`` for the counterpart greeting to THIS round,
    consuming a stash left by an earlier round's wait first."""
    deadline = asyncio.get_event_loop().time() + timeout
    last: Refused | None = None
    while True:
        if sub_game_number in pending:
            raw = pending.pop(sub_game_number)
        else:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise _budget_exhausted(last)
            try:
                raw = await asyncio.wait_for(negotiate_q.get(), timeout=remaining)
            except TimeoutError:
                raise _budget_exhausted(last) from None

        raw_round = raw.get("sub_game_number") if isinstance(raw, dict) else None
        if isinstance(raw_round, int) and raw_round != sub_game_number:
            # A future (or, rarely, redelivered stale) round's greeting --
            # never this round's answer. Preserve it; do not verify it here.
            pending[raw_round] = raw
            continue
        try:
            return verify_greeting(greeting, raw)
        except Refused as exc:
            last = exc
            if exc.code not in ("SPAR-N06", "SPAR-N07"):
                raise
            # A same-numbered bystander (role collision) -- keep waiting for
            # our actual counterpart, exactly as the kit's handshake() does.


def _budget_exhausted(last: Refused | None) -> Refused:
    suffix = f" (last refusal {last.code})" if last else ""
    return Refused("SPAR-N09", "handshake budget exhausted; our counterpart never arrived" + suffix)
