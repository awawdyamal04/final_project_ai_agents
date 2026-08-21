"""Reference-v3 adapter -- the at-least-once delivery contract (SPEC
section 7.1, PROMOTED): absorb / equivocation / apply / buffer / violation /
discard, keyed on the commit value, not ``(kind, step)``.
"""

from __future__ import annotations

import pytest

from police_thief.interop.delivery import Equivocation, Inbox, ProtocolViolation


def _msg(step: int, commit: str = "c") -> dict:
    return {"step": step, "commit": commit}


def test_apply_then_absorb_redelivery():
    inbox = Inbox(window=4)
    ready = inbox.offer(_msg(1, "aaa"))
    assert [m["step"] for m in ready] == [1]
    again = inbox.offer(_msg(1, "aaa"))  # same commit: redelivery
    assert again == []
    assert inbox.played == {1: "aaa"}


def test_equivocation_on_different_commit_for_played_step():
    inbox = Inbox(window=4)
    inbox.offer(_msg(1, "aaa"))
    with pytest.raises(Equivocation):
        inbox.offer(_msg(1, "bbb"))


def test_buffer_holds_out_of_order_arrival_inside_window():
    inbox = Inbox(window=4)
    ready = inbox.offer(_msg(3, "ccc"))
    assert ready == []
    assert 3 in inbox.buffered
    assert inbox.next_step == 1


def test_buffer_drains_in_order_once_the_gap_fills():
    inbox = Inbox(window=4)
    inbox.offer(_msg(3, "ccc"))
    inbox.offer(_msg(2, "bbb"))
    ready = inbox.offer(_msg(1, "aaa"))
    assert [m["step"] for m in ready] == [1, 2, 3]
    assert inbox.next_step == 4


def test_violation_past_the_reorder_window():
    inbox = Inbox(window=2)
    with pytest.raises(ProtocolViolation):
        inbox.offer(_msg(5, "eee"))


def test_zero_window_makes_any_out_of_order_arrival_a_violation():
    """A legitimate negotiated choice, not a bug -- App. E rule 35 puts the
    self-inflicted risk on the strict receiver, not the sender."""
    inbox = Inbox(window=0)
    with pytest.raises(ProtocolViolation):
        inbox.offer(_msg(2, "bbb"))


def test_discard_for_a_stale_never_played_step_below_next():
    """A step below ``next`` that was never played can never become
    applicable -- must not silently sit in the buffer forever
    (anrbj666's 2026-08-04 finding)."""
    inbox = Inbox(window=4, next_step=5)
    ready = inbox.offer(_msg(2, "bbb"))
    assert ready == []
    assert 2 not in inbox.buffered
