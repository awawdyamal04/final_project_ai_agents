"""The full sparring series (Phase C): negotiate -> play -> audit, repeated
for each sub-game in turn, without restarting this peer process.

**Role alternation.** ``role_for`` -- odd sub-games play the declared
natural role, even ones the opposite -- is the reference implementation's
own rule, not stated in the book's body (SPEC/``sparring/rules/outcome.py``
docstring); reimplemented here rather than imported, since the kit is not a
project dependency. Reset per sub-game: a fresh :class:`GameSessionV3`
(inbox, sealed records, nonces all start clean). Persisted across every
sub-game: peer identity (``group_id``), the agreed terms, the alternation
rule itself, the pinned opponent identity and derived ``game_uid``, and --
Phase B -- the one outbound connection. Row/result shapes live in
:mod:`series_types_v3`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from police_thief.domain.enums import Role
from police_thief.interop.exceptions import Refused
from police_thief.interop.game_session import GameSessionV3
from police_thief.interop.locked_models import declarable_locks
from police_thief.interop.negotiation import build_greeting, to_wire
from police_thief.interop.outbound import OutboundSession
from police_thief.interop.series_audit_v3 import await_matching_audit
from police_thief.interop.series_negotiate_v3 import negotiate_round
from police_thief.interop.series_types_v3 import SeriesResult, SubGameRow
from police_thief.interop.turnloop_v3 import play_to_outcome
from police_thief.interop.wire import audit_payload


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def role_for(natural: Role, sub_game_number: int) -> Role:
    """Odd sub-games play ``natural``; even ones play the opposite."""
    return natural if sub_game_number % 2 == 1 else natural.opponent


def _drain(queue: asyncio.Queue) -> None:
    """Discard anything left in the TURN channel once a round has settled
    -- mirrors the kit's own ``inboxes.turns.clear()`` (``netplay.py``,
    right after a round's audit exchange): a stray turn-channel message the
    opponent sent while we were still settling must not be read as the next
    round's first move. The kit clears *only* this one channel -- never
    negotiate/agreements or audits, both of which may legitimately carry a
    future round's message before we are ready for it (see
    ``series_negotiate_v3``/``series_audit_v3``, which stash rather than
    drop those instead)."""
    while not queue.empty():
        queue.get_nowait()


async def run_series(
    state,
    *,
    outbound: OutboundSession | None,
    timeout: float,
    sub_games: int,
) -> SeriesResult:
    result = SeriesResult()
    natural = Role(state.role_hint)
    # One series, one opponent (kit: ``known_opponent`` in ``netplay.py``).
    # Unset through sub-game 1 -- the opponent is not pinned yet, so that
    # greeting omits game_uid; every greeting from sub-game 2 on declares
    # the uid derived against the now-known opponent, and a different group
    # answering later refuses the series rather than being aggregated in.
    known_opponent: str | None = None
    negotiate_pending: dict[int, object] = {}
    audit_pending: dict[int, object] = {}

    for n in range(1, sub_games + 1):
        role = role_for(natural, n)
        state.sink.emit("sub_game_negotiate_start", sub_game_number=n, role=role.value)
        _drain(state.turn_q)

        greeting = build_greeting(
            state.config, group_id=state.group_id, role=role.value, sub_game_number=n,
            locks=declarable_locks(), opponent_group=known_opponent,
        )
        if outbound is not None:
            await outbound.call(
                "negotiate", "message", to_wire(greeting), retry_for=120.0 if n == 1 else 20.0
            )
        try:
            agreed = await negotiate_round(
                state.negotiate_q, greeting, sub_game_number=n, timeout=timeout,
                pending=negotiate_pending,
            )
        except Refused as exc:
            result.refusal = str(exc)
            break
        if known_opponent is not None and agreed.opponent_group != known_opponent:
            result.refusal = (
                f"sub-game {n}: a DIFFERENT group ({agreed.opponent_group!r}) answered a "
                f"series opened with {known_opponent!r} -- refusing to mix two opponents "
                f"into one series"
            )
            break
        known_opponent = agreed.opponent_group
        if result.game_id is None:
            result.game_id, result.game_uid = agreed.game_id, agreed.game_uid

        session = GameSessionV3(
            role=role, config=state.config, sub_game_number=n, clock_stamp=_now_iso
        )
        state.session = session
        max_rounds = state.config.movement_and_barriers.max_moves
        await play_to_outcome(
            session, outbound=outbound, timeout=timeout,
            turn_q=state.turn_q, max_rounds=max_rounds, sink=state.sink,
        )
        local_terminal = session.outcome or "timeout"

        mine = audit_payload(
            sender=role.value, records=session.records, result_claim=local_terminal
        )
        if outbound is not None:
            await outbound.call("submit_audit", "payload", mine)
        audit = await await_matching_audit(
            state.audit_q, sub_game_number=n, played=session.inbox.played,
            timeout=timeout, sink=state.sink, pending=audit_pending,
        )

        # Labels agreeing is not enough (this is the Phase F gap): a
        # present-but-cryptographically-failed audit must not be read as
        # "agreed" just because ``result_claim`` happens to match -- the
        # kit's own ``settled_outcome`` never trusts a failed audit's claim
        # either, it becomes ``tamper_forfeit`` instead. ``timeout`` is the
        # one local outcome the kit settles WITHOUT an audit at all (a
        # classified zeroed sub-game owes no reveal).
        verified_ok = local_terminal == "timeout" or audit.audit_status == "verified"
        row = SubGameRow(
            sub_game_number=n, role=role.value, local_terminal=local_terminal,
            remote_terminal=audit.remote_terminal, audit_status=audit.audit_status,
            agreement=(audit.remote_terminal == local_terminal and verified_ok),
        )
        result.rows.append(row)
        state.sink.emit(
            "sub_game_row", sub_game_number=n, local_terminal=local_terminal,
            remote_terminal=audit.remote_terminal, audit_status=audit.audit_status,
            agreement=row.agreement, next_round_already_queued=(n + 1) in negotiate_pending,
        )

    result.settled = len(result.rows) == sub_games and all(r.agreement for r in result.rows)
    return result
