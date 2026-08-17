"""Domain wiring for capture_claim (E-21): a thief answering truthfully, using
the exact same pure functions the offline harness and replay already use.

Two grounds are fully self-sufficient live (from the thief's own
``LocalState`` alone): ``barrier_on_thief`` and ``no_legal_move``, covered
here. The third, ``landed``, is structurally unverifiable without the cop's
true position (E-8/E-9) -- see ``test_capture_claim_landed.py``, split out
purely to stay under the 150-line lecturer limit."""

from __future__ import annotations

from police_thief.domain.capture_claim import (
    CLAIM_KIND_BARRIER_ON_THIEF,
    CLAIM_KIND_NO_LEGAL_MOVE,
    claim_kind_for_reason,
    reason_for_claim_kind,
    thief_truthful_verdict,
)
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason
from tests.domain.conftest import place_at, wall_in

# ----------------------------------------------------------------------
# Wire vocabulary <-> domain CaptureReason
# ----------------------------------------------------------------------


def test_claim_kind_reason_mapping_is_a_bijection():
    for reason in CaptureReason:
        kind = claim_kind_for_reason(reason)
        assert reason_for_claim_kind(kind) is reason


# ----------------------------------------------------------------------
# barrier_on_thief -- self-sufficient live
# ----------------------------------------------------------------------


def test_barrier_on_thief_confirmed_when_true(thief_state):
    thief_here = place_at(thief_state, 3, 3)
    verdict = thief_truthful_verdict(
        CLAIM_KIND_BARRIER_ON_THIEF, thief_here, None,
        barrier_cell=Coordinate(3, 3),
    )
    assert verdict.captured
    assert verdict.reason is CaptureReason.BARRIER_ON_THIEF


def test_barrier_on_thief_denied_when_elsewhere(thief_state):
    thief_here = place_at(thief_state, 3, 3)
    verdict = thief_truthful_verdict(
        CLAIM_KIND_BARRIER_ON_THIEF, thief_here, None,
        barrier_cell=Coordinate(3, 4),
    )
    assert not verdict.captured


def test_barrier_on_thief_without_a_barrier_cell_is_never_confirmed(thief_state):
    """No barrier_cell supplied -- honestly reports no capture rather than
    guessing (mirrors ``CaptureVerdict.none()``)."""
    verdict = thief_truthful_verdict(
        CLAIM_KIND_BARRIER_ON_THIEF, thief_state, None, barrier_cell=None
    )
    assert not verdict.captured


# ----------------------------------------------------------------------
# no_legal_move -- self-sufficient live
# ----------------------------------------------------------------------


def test_no_legal_move_confirmed_when_trapped(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3), (4, 3), (3, 4), (3, 2)])
    verdict = thief_truthful_verdict(
        CLAIM_KIND_NO_LEGAL_MOVE, walled, shared_config
    )
    assert verdict.captured
    assert verdict.reason is CaptureReason.THIEF_HAS_NO_LEGAL_MOVE


def test_no_legal_move_denied_when_an_escape_exists(thief_state, shared_config):
    walled = wall_in(thief_state, [(2, 3), (4, 3), (3, 4)])
    verdict = thief_truthful_verdict(
        CLAIM_KIND_NO_LEGAL_MOVE, walled, shared_config
    )
    assert not verdict.captured
