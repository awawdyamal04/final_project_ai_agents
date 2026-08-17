"""Domain wiring for capture_claim (E-21): the ``landed`` ground (cop lands
on the thief) and ``verdict_confirms_claim``. Split out of
``test_capture_claim.py`` purely to stay under the 150-line lecturer limit.

``landed`` needs the cop's true position -- structurally unavailable to the
thief (E-8/E-9) -- so ``thief_truthful_verdict`` must raise rather than guess
when ``movement`` is not supplied. (The peer layer maps that raise onto the
``audit_required`` wire value -- see
``tests/peer/test_capture_claim_landed.py`` -- this file only tests the pure
domain function's own contract: raise, or answer honestly.)"""

from __future__ import annotations

import pytest

from police_thief.domain.capture import CaptureVerdict
from police_thief.domain.capture_claim import (
    CLAIM_KIND_BARRIER_ON_THIEF,
    CLAIM_KIND_LANDED,
    thief_truthful_verdict,
    verdict_confirms_claim,
)
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason
from police_thief.domain.exceptions import CaptureClaimUnverifiableError
from police_thief.domain.simultaneity import TurnMovement


def movement(cop_before, cop_after, thief_before, thief_after) -> TurnMovement:
    return TurnMovement(
        cop_before=Coordinate(*cop_before),
        cop_after=Coordinate(*cop_after),
        thief_before=Coordinate(*thief_before),
        thief_after=Coordinate(*thief_after),
    )


# ----------------------------------------------------------------------
# landed -- structurally unverifiable live without an explicit movement
# ----------------------------------------------------------------------


def test_landed_claim_without_movement_raises_rather_than_guesses(
    thief_state, shared_config
):
    with pytest.raises(CaptureClaimUnverifiableError, match="never legitimately has"):
        thief_truthful_verdict(CLAIM_KIND_LANDED, thief_state, shared_config)


def test_landed_claim_confirmed_when_movement_is_supplied(thief_state, shared_config):
    mv = movement((3, 2), (3, 3), (3, 3), (3, 3))
    verdict = thief_truthful_verdict(
        CLAIM_KIND_LANDED, thief_state, shared_config, movement=mv
    )
    assert verdict.captured
    assert verdict.reason is CaptureReason.COP_LANDED_ON_THIEF


def test_landed_claim_denied_when_movement_shows_no_collision(
    thief_state, shared_config
):
    mv = movement((0, 0), (0, 1), (3, 3), (3, 4))
    verdict = thief_truthful_verdict(
        CLAIM_KIND_LANDED, thief_state, shared_config, movement=mv
    )
    assert not verdict.captured


def test_unknown_claim_kind_raises_value_error(thief_state, shared_config):
    with pytest.raises(ValueError, match="unknown claim_kind"):
        thief_truthful_verdict("teleport", thief_state, shared_config)


# ----------------------------------------------------------------------
# verdict_confirms_claim -- both the fact and the ground must match
# ----------------------------------------------------------------------


def test_confirms_when_fact_and_ground_both_match():
    verdict = CaptureVerdict.by(CaptureReason.BARRIER_ON_THIEF)
    assert verdict_confirms_claim(verdict, CLAIM_KIND_BARRIER_ON_THIEF)


def test_does_not_confirm_when_ground_differs():
    """A thief genuinely trapped is not confirming a 'landed' claim."""
    verdict = CaptureVerdict.by(CaptureReason.THIEF_HAS_NO_LEGAL_MOVE)
    assert not verdict_confirms_claim(verdict, CLAIM_KIND_LANDED)


def test_does_not_confirm_when_no_capture_occurred():
    assert not verdict_confirms_claim(
        CaptureVerdict(captured=False), CLAIM_KIND_BARRIER_ON_THIEF
    )
