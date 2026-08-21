"""The turn-exchange leg of one reference-v3 sub-game: alternate
``take_turn``/``receive_turn`` until an outcome is reached, instrumenting
each leg on the adapter's own :class:`EventSink` (Phase A diagnostics --
operational telemetry only, never the cryptographic audit chain).

Split out of ``orchestrator.py`` to keep that file under the project's
150-line limit; this is the one concern (the actual message ping-pong) that
grows once instrumented properly, so it gets its own file rather than
trimming the diagnostics down to fit.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from police_thief.interop.game_receive import receive_turn
from police_thief.interop.game_session import GameSessionV3
from police_thief.interop.outbound import OutboundSession
from police_thief.peer.events import EventSink


async def play_to_outcome(
    session: GameSessionV3,
    *,
    outbound: OutboundSession | None,
    timeout: float,
    turn_q: asyncio.Queue,
    max_rounds: int,
    sink: EventSink,
) -> None:
    """Drive ``session`` to a decided outcome (or ``max_rounds``), sending
    and receiving reference-v3 turn messages. Leaves ``session.outcome`` and
    ``session.records`` as the caller's source of truth; raises nothing of
    its own beyond what ``receive_turn``/the outbound call already raise.
    """

    async def _send_next() -> None:
        # ``take_turn`` returns ``None`` once outcome is decided and this
        # side has nothing left to say (terminal_v3.terminal_message) --
        # e.g. the cop after adjudicating the thief's own concession.
        was_open = session.outcome is None
        outbound_msg = session.take_turn()
        if was_open and session.outcome is not None:
            sink.emit("local_terminal_decision", outcome=session.outcome, step=session.step)
        if outbound_msg is not None and outbound is not None:
            deadline_at = time.monotonic() + timeout
            await outbound.call("receive_turn", "message", outbound_msg, deadline_at=deadline_at)

    if session.opens:
        await _send_next()

    while session.outcome is None and session.step < max_rounds:
        raw: Any = await asyncio.wait_for(turn_q.get(), timeout=timeout)
        sink.emit(
            "remote_turn_received", step=raw.get("step"),
            carries_claim_response=raw.get("claim_response") is not None,
            carries_win_claim=raw.get("win_claim") is not None,
        )
        receive_turn(session, raw)
        await _send_next()
