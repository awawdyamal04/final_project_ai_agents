"""Regression tests for two real live-run bugs, both in the audit exchange
of a sparring series.

**Phase F.** A sub-game that timed out on both sides delivered its audit
late enough to arrive during the *next* round's window. The pre-Phase-F
code read "whatever is next in the queue" as the current round's answer,
misattributing round 4's late ``timeout`` audit to round 5.

**Phase H.** The Phase F fix then *discarded* the mismatched straggler
instead of preserving it -- which just moved the data loss one level
down: a genuine early arrival for a round not yet reached, or the real
round-4 answer arriving after round 4 already gave up waiting, was gone
for good. ``await_matching_audit`` must stash a mismatch under its own
round (``pending``) rather than drop it, so a round that starts after its
own audit already arrived finds it waiting.
"""

from __future__ import annotations

import asyncio

import pytest

from police_thief.interop.audit_adapter import seal_record
from police_thief.interop.series_audit_v3 import audit_round, await_matching_audit
from police_thief.interop.wire import audit_payload
from police_thief.peer.events import MemoryEventSink


def _payload(sub_game: int, result_claim: str, *, key: str = "sub_game") -> dict:
    record = seal_record({key: sub_game, "step": 1, "role": "police", "action": "MOVE:N"})
    return audit_payload(sender="police", records=[record], result_claim=result_claim)


def test_audit_round_reads_our_own_schema_key():
    payload = _payload(4, "timeout", key="sub_game")
    assert audit_round(payload) == 4


def test_audit_round_reads_the_reference_schema_key():
    payload = _payload(4, "timeout", key="sub_game_number")
    assert audit_round(payload) == 4


def test_audit_round_is_none_for_an_empty_chain():
    payload = audit_payload(sender="police", records=[], result_claim="timeout")
    assert audit_round(payload) is None


@pytest.mark.asyncio
async def test_a_stale_round_is_stashed_not_misattributed():
    """The exact live shape: round 4's late ``timeout`` audit must not be
    read as round 5's answer when round 5's own audit is genuinely still
    pending or arrives after -- and, unlike the Phase F version of this
    fix, round 4's straggler must still be sitting in ``pending`` afterward
    rather than having been thrown away (task C)."""
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_payload(4, "timeout"))  # a round-4 straggler
    await queue.put(_payload(5, "capture"))  # round 5's real answer

    sink = MemoryEventSink()
    pending: dict = {}
    outcome = await await_matching_audit(
        queue, sub_game_number=5, played={}, timeout=2.0, sink=sink, pending=pending
    )
    assert outcome.remote_terminal == "capture"
    assert "audit_round_stashed" in sink.names()
    assert 4 in pending  # preserved, not deleted


@pytest.mark.asyncio
async def test_a_stashed_round_is_found_without_touching_the_queue():
    """Task A/B: if round 4's straggler was stashed during an earlier
    round's wait, round 4 itself (were it to ask again) must be answered
    from the stash immediately -- never re-polling a queue that no longer
    holds it."""
    queue: asyncio.Queue = asyncio.Queue()
    pending: dict = {4: _payload(4, "timeout")}
    outcome = await await_matching_audit(
        queue, sub_game_number=4, played={}, timeout=0.2, sink=MemoryEventSink(), pending=pending
    )
    assert outcome.remote_terminal == "timeout"
    assert 4 not in pending  # consumed exactly once
    assert queue.empty()  # never touched -- the answer came from the stash


@pytest.mark.asyncio
async def test_current_round_audit_already_queued_before_we_wait_still_verifies():
    """Task B: an audit that arrived before this round even started waiting
    for it (queued ahead of the call, not pending from a prior stash) must
    still verify -- ``asyncio.Queue.get`` returns already-queued items
    immediately, so this is a regression guard against ever changing that."""
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_payload(1, "capture"))
    outcome = await await_matching_audit(
        queue, sub_game_number=1, played={}, timeout=0.2, sink=MemoryEventSink(), pending={}
    )
    assert outcome.remote_terminal == "capture"


@pytest.mark.asyncio
async def test_no_matching_audit_arrives_reports_no_audit():
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_payload(4, "timeout"))  # only a stale round-4 straggler

    sink = MemoryEventSink()
    outcome = await await_matching_audit(
        queue, sub_game_number=5, played={}, timeout=0.3, sink=sink, pending={}
    )
    assert outcome.remote_terminal is None
    assert outcome.audit_status == "no_audit"


@pytest.mark.asyncio
async def test_an_unparsable_round_is_accepted_not_discarded():
    """A payload with no records (round unknown) is treated as answering
    the round we asked about, not as a mismatch -- matches the pre-fix
    lenient behaviour for a degenerate, zero-step sub-game."""
    queue: asyncio.Queue = asyncio.Queue()
    empty = audit_payload(sender="police", records=[], result_claim="survival")
    await queue.put(empty)

    outcome = await await_matching_audit(
        queue, sub_game_number=1, played={}, timeout=1.0, sink=MemoryEventSink(), pending={}
    )
    assert outcome.remote_terminal == "survival"
