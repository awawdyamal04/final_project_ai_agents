"""Capture under reference-v3's wire (SPEC section 3.1: answer vs.
concession), built on this project's existing, already-tested domain
functions -- no new capture-detection logic, only the reference-v3-specific
dispatch.

The one structural difference from this project's native protocol: under
reference-v3 the cop's ``capture_claim`` field carries the claimed cell
``[r, c]`` **on the wire**, so a "landed" claim is self-verifiable by direct
coordinate equality. Natively that cell never crosses the wire at all (see
``domain/capture_claim.py``'s docstring), which is why the native path needs
``CaptureClaimUnverifiableError`` and this one does not.
"""

from __future__ import annotations

from police_thief.config.models import SharedConfig
from police_thief.domain.capture import (
    CaptureVerdict,
    evaluate_barrier_capture,
    evaluate_trapped_capture,
)
from police_thief.domain.enums import CaptureReason
from police_thief.domain.state import LocalState


def answer_landed_claim(claim: list[int] | None, thief_state: LocalState) -> dict | None:
    """The thief's obligatory, truthful answer to a police "landed" claim
    (E-21/E-22): direct equality against its own real position -- the only
    input a truthful thief needs, and the only one it has."""
    if claim is None:
        return None
    caught = list(thief_state.position.as_list()) == list(claim)
    return {"claim": list(claim), "caught": caught}


def self_report_concession(
    thief_state: LocalState,
    config: SharedConfig,
    *,
    barrier_just_placed: tuple[int, int] | None,
) -> dict | None:
    """A rule-46/47 ending only the thief can see, said out loud so the cop
    (which cannot see the board) does not wait out its budget for a turn
    that will never come. Distinct from an *answer*: this names the thief's
    own final cell, not the cell the cop claimed (SPEC section 3.1)."""
    verdict = _self_capture_verdict(thief_state, config, barrier_just_placed)
    if not verdict:
        return None
    return {"claim": list(thief_state.position.as_list()), "caught": True}


def _self_capture_verdict(
    thief_state: LocalState,
    config: SharedConfig,
    barrier_just_placed: tuple[int, int] | None,
) -> CaptureVerdict:
    if barrier_just_placed is not None:
        from police_thief.domain.coordinates import Coordinate

        verdict = evaluate_barrier_capture(
            Coordinate(*barrier_just_placed), thief_state.position
        )
        if verdict:
            return verdict
    return evaluate_trapped_capture(thief_state, config)


def claim_response_reason(response: dict | None) -> CaptureReason | None:
    """Best-effort classification of an inbound ``claim_response`` for
    logging/audit -- not used to decide capture, only to label it."""
    if not response or not response.get("caught"):
        return None
    return CaptureReason.COP_LANDED_ON_THIEF
