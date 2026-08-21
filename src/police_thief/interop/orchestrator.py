"""Background worker: negotiate, play the turn loop, exchange the audit --
against a real reference-v3 opponent over MCP (SPEC section 7.5).

One asyncio task per mounted adapter (see ``reference_v3.py``), and (Phase
B) one persistent :class:`OutboundSession` for its entire lifetime --
negotiation, every turn, and the audit exchange all share the one
connection rather than each opening and closing its own.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from police_thief.config.models import SharedConfig
from police_thief.domain.enums import Role
from police_thief.interop.audit_adapter import verify_audit
from police_thief.interop.exceptions import Refused
from police_thief.interop.game_session import GameSessionV3
from police_thief.interop.locked_models import declarable_locks
from police_thief.interop.negotiation import Agreed, build_greeting, to_wire, verify_greeting
from police_thief.interop.outbound import OutboundSession
from police_thief.interop.series_v3 import SeriesResult, run_series
from police_thief.interop.turnloop_v3 import play_to_outcome
from police_thief.interop.wire import audit_payload
from police_thief.peer.events import EventSink, NullEventSink


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ReferenceV3Result:
    agreed: Agreed | None = None
    refusal: str | None = None
    outcome: str | None = None
    records: int = 0
    audit_verified: bool | None = None
    audit_mismatches: tuple[str, ...] = ()
    error: str | None = None
    """An infrastructure failure (a connection that never recovered inside
    its retry budget, an unexpected exception) -- distinct from ``refusal``,
    which means the opponent's own greeting was understood and rejected."""
    series: SeriesResult | None = None
    """Populated instead of the single-game fields above when
    ``ReferenceV3State.sub_games > 1`` (Phase C)."""


@dataclass
class ReferenceV3State:
    config: SharedConfig
    group_id: str
    role_hint: str
    opponent_url: str | None
    sub_games: int = 1
    negotiate_q: asyncio.Queue = field(default_factory=asyncio.Queue)
    turn_q: asyncio.Queue = field(default_factory=asyncio.Queue)
    audit_q: asyncio.Queue = field(default_factory=asyncio.Queue)
    control_q: asyncio.Queue = field(default_factory=asyncio.Queue)
    result: ReferenceV3Result = field(default_factory=ReferenceV3Result)
    session: GameSessionV3 | None = None
    sink: EventSink = field(default_factory=NullEventSink)


async def run(state: ReferenceV3State, *, timeout: float = 60.0) -> ReferenceV3Result:
    """Negotiate, play one sub-game, exchange audits. Never raises: every
    failure -- a protocol refusal, or an infrastructure fault such as a
    retry budget exhausted while the opponent's edge never came up -- is
    recorded on ``state.result`` for the caller to inspect, rather than
    left as an unretrieved exception on the background task. Opens one
    :class:`OutboundSession` for the whole call and always closes it,
    including on the exceptional path -- a leaked HTTP session on an
    otherwise-recorded failure would itself be a bug Phase B exists to
    remove, not just relocate."""
    outbound = OutboundSession(state.opponent_url, sink=state.sink) if state.opponent_url else None
    try:
        if state.sub_games > 1:
            # Phase C: the full series, one persistent connection, this
            # peer never restarted between sub-games.
            state.result.series = await run_series(
                state, outbound=outbound, timeout=timeout, sub_games=state.sub_games
            )
            return state.result
        return await _run_inner(state, timeout=timeout, outbound=outbound)
    except Exception as exc:  # noqa: BLE001 - genuinely the last-resort boundary
        state.result.error = f"{type(exc).__name__}: {exc}"
        return state.result
    finally:
        if outbound is not None:
            await outbound.close()


async def _run_inner(
    state: ReferenceV3State, *, timeout: float, outbound: OutboundSession | None
) -> ReferenceV3Result:
    greeting = build_greeting(
        state.config, group_id=state.group_id, role=state.role_hint, sub_game_number=1,
        locks=declarable_locks(),
    )
    if outbound is not None:
        # The single highest-risk startup race: two independently launched
        # processes, neither knowing when the other will finish binding its
        # port (this project's own peer, in particular, spends up to ~10s on
        # its native handshake attempt before even starting its server --
        # see peer/run.py -- entirely unrelated to reference-v3 readiness).
        # A generous, one-time retry budget here costs nothing once the
        # opponent is actually up.
        await outbound.call("negotiate", "message", to_wire(greeting), retry_for=120.0)

    raw_greeting = await asyncio.wait_for(state.negotiate_q.get(), timeout=timeout)
    try:
        agreed = verify_greeting(greeting, raw_greeting)
    except Refused as exc:
        state.result.refusal = str(exc)
        return state.result
    state.result.agreed = agreed

    session = GameSessionV3(
        role=Role(state.role_hint), config=state.config, sub_game_number=1, clock_stamp=_now_iso
    )
    state.session = session
    max_rounds = state.config.movement_and_barriers.max_moves

    await play_to_outcome(
        session, outbound=outbound, timeout=timeout,
        turn_q=state.turn_q, max_rounds=max_rounds, sink=state.sink,
    )

    state.result.outcome = session.outcome or "timeout"
    state.result.records = len(session.records)
    state.sink.emit("sub_game_settled", outcome=state.result.outcome, step=session.step)

    mine = audit_payload(
        sender=state.role_hint, records=session.records, result_claim=state.result.outcome
    )
    if outbound is not None:
        await outbound.call("submit_audit", "payload", mine)
    try:
        theirs = await asyncio.wait_for(state.audit_q.get(), timeout=timeout)
        outcome = verify_audit(theirs, played=session.inbox.played)
        state.result.audit_verified = outcome.verified
        state.result.audit_mismatches = outcome.mismatches
    except TimeoutError:
        state.result.audit_verified = None
    return state.result
