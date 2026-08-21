"""One sub-game's audit exchange within a series (split out of
:mod:`series_v3` to keep that file under the 150-line limit): submit our
own sealed chain, then wait for the opponent's.

**Stash, never discard (kit parity, ``netplay.py``).** The reference kit's
own driver never bulk-clears its audits queue and never round-tags what it
pops -- it trusts strict per-round lockstep (both sides fully settle round
N, audit included, before either opens round N+1's handshake) and lets a
genuinely mismatched reveal fail the *cryptographic* binding check instead
of being filtered out first. An earlier version of this file added its own
round-tag filter that *discarded* a mismatched arrival outright -- which
built exactly the failure mode it was meant to prevent, one level up: a
stray straggler consumed and dropped is a straggler that can never answer
the round it actually belonged to, and a genuine early arrival for a round
we have not reached yet was lost the same way. The fix keeps the round-tag
check (useful: it means a mismatch never has to survive a wasted, doomed
verification against the wrong round's ``played`` map) but stashes what it
finds instead of throwing it away, keyed by the round it says it belongs
to -- ``pending`` is owned by the caller and lives for the whole series, so
a round that starts after its own audit already arrived finds it waiting.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from police_thief.interop.audit_adapter import verify_audit
from police_thief.peer.events import EventSink


def audit_round(payload: dict) -> int | None:
    """Which sub-game an inbound ``AuditPayload`` actually belongs to, read
    off its own first sealed record (each side's own schema: this
    project's own records key it ``sub_game``, the reference's key it
    ``sub_game_number``) -- ``None`` if it cannot be determined (an empty
    chain), which is treated as unknown rather than a mismatch."""
    records = payload.get("records") or []
    if not records:
        return None
    inner = records[0].get("payload") or {}
    return inner.get("sub_game_number", inner.get("sub_game"))


@dataclass
class AuditOutcome:
    remote_terminal: str | None
    audit_status: str  # "verified" | "unverified" | "no_audit"


async def await_matching_audit(
    audit_q: asyncio.Queue, *, sub_game_number: int, played: dict, timeout: float,
    sink: EventSink, pending: dict[int, Any],
) -> AuditOutcome:
    """Wait up to ``timeout`` for the audit tagged for ``sub_game_number``,
    consuming a stash left by an earlier round's wait first, and stashing
    (never dropping) anything tagged for a different round."""
    if sub_game_number in pending:
        theirs = pending.pop(sub_game_number)
    else:
        deadline = asyncio.get_event_loop().time() + timeout
        theirs = None
        while theirs is None:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return AuditOutcome(remote_terminal=None, audit_status="no_audit")
            try:
                candidate = await asyncio.wait_for(audit_q.get(), timeout=remaining)
            except TimeoutError:
                return AuditOutcome(remote_terminal=None, audit_status="no_audit")
            got_round = audit_round(candidate)
            if got_round is not None and got_round != sub_game_number:
                sink.emit("audit_round_stashed", expected=sub_game_number, got=got_round)
                pending[got_round] = candidate
                continue
            theirs = candidate

    check = verify_audit(theirs, played=played)
    return AuditOutcome(
        remote_terminal=theirs.get("result_claim"),
        audit_status="verified" if check.verified else "unverified",
    )
