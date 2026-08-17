"""Replay-time capture_claim check (E-21, E-22): the ``landed`` ground when
the thief answered ``audit_required`` live.

``audit_required`` asserts nothing, so ``check_capture_claims`` never flags
it as a disagreement (rightly -- nobody lied). But the claim's truth is
still fully determined: ``terminal`` is the same independent reconstruction
every other ground uses, so comparing the claim's kind/turn against it tells
the authoritative story regardless of what the live response said. That is
what these tests demonstrate -- both directions.

Split out of ``test_capture_claim_check.py`` purely to stay under the
150-line lecturer limit; reuses its ``claim_record``/``response_record``
helpers."""

from __future__ import annotations

from police_thief.domain.capture_claim import CLAIM_KIND_LANDED, claim_kind_for_reason
from police_thief.domain.enums import CaptureReason
from police_thief.domain.terminal import capture as terminal_capture
from police_thief.protocol.capture_claim import VERDICT_AUDIT_REQUIRED
from police_thief.replay.capture_claim_check import check_capture_claims
from tests.replay.test_capture_claim_check import claim_record, response_record


def test_replay_verifies_a_truthful_landed_claim():
    """The cop's landed claim was in fact true. audit_required reported no
    verdict either way, but the reconstruction settles it."""
    terminal = terminal_capture(5, CaptureReason.COP_LANDED_ON_THIEF)
    claim = claim_record(turn=5, claim_kind=CLAIM_KIND_LANDED)
    response = response_record(verdict=VERDICT_AUDIT_REQUIRED)

    disagreements = check_capture_claims([claim], [response], terminal)
    assert disagreements == []  # audit_required is never itself a lie

    # The authoritative answer, from terminal alone:
    assert terminal.is_capture
    assert claim_kind_for_reason(terminal.capture_reason) == claim["payload"]["claim_kind"]


def test_replay_detects_a_false_landed_claim():
    """The cop's landed claim was in fact false (the real terminal was a
    different ground entirely). Still not a disagreement -- audit_required
    asserted nothing -- but still detectable from terminal."""
    terminal = terminal_capture(5, CaptureReason.THIEF_HAS_NO_LEGAL_MOVE)
    claim = claim_record(turn=5, claim_kind=CLAIM_KIND_LANDED)
    response = response_record(verdict=VERDICT_AUDIT_REQUIRED)

    disagreements = check_capture_claims([claim], [response], terminal)
    assert disagreements == []

    # The authoritative answer, from terminal alone: the claim was false.
    assert claim_kind_for_reason(terminal.capture_reason) != claim["payload"]["claim_kind"]


def test_replay_detects_a_false_landed_claim_when_no_capture_happened_at_all():
    claim = claim_record(turn=5, claim_kind=CLAIM_KIND_LANDED)
    response = response_record(verdict=VERDICT_AUDIT_REQUIRED)

    disagreements = check_capture_claims([claim], [response], terminal=None)
    assert disagreements == []  # still not a lie -- audit_required asserted nothing
