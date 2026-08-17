"""Live-side wiring over the existing pure capture-evaluation functions,
for a thief answering a ``CAPTURE_CLAIM`` truthfully (E-21).

No new capture-detection logic -- every ground is decided by the exact same
functions :mod:`police_thief.domain.capture` already uses for the offline
harness (Phase 1) and the replay verifier (prd.md Sec 14.9). What is new
here is only the *dispatch*: which existing function answers which claim
kind, and what a live peer can honestly supply it.

Two of the three grounds are fully self-sufficient live, from the thief's
own ``LocalState`` alone:

* ``barrier_on_thief`` (E-46) -- the barrier's cell is public once revealed
  (E-15/E-16); the thief's own cell is always its own.
* ``no_legal_move`` (E-47) -- needs only the thief's own state and the
  (fully public) barrier set.

The third, ``landed`` (cop-on-thief collision), needs the cop's *true*
position, which E-8/E-9 structurally forbid ever reaching the thief's
process -- not even the cop's own claimed cell is on the wire (prd.md
Sec 14.6/14.7 dropped it deliberately). A live peer genuinely cannot verify
this ground from first principles under the current architecture; see
``CaptureClaimUnverifiableError``'s docstring. This module does not paper
over that gap: it requires the caller to supply the reconstructed
``TurnMovement`` explicitly for a ``landed`` claim, and raises rather than
guessing if it is not available. The offline replay (which does have both
positions) remains authoritative for this ground -- D-41 augmented, not
replaced.

The wire vocabulary (``claim_kind`` strings) is owned here, not in
``protocol/``, because it is fundamentally a labelling of
:class:`~police_thief.domain.enums.CaptureReason` -- a domain concept.
``protocol/capture_claim.py`` imports it from here, keeping the dependency
direction the same as everywhere else in this codebase (protocol depends on
domain, never the reverse).
"""

from __future__ import annotations

from police_thief.config.models import SharedConfig
from police_thief.domain.capture import (
    CaptureVerdict,
    evaluate_barrier_capture,
    evaluate_movement_capture,
    evaluate_trapped_capture,
)
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason
from police_thief.domain.exceptions import CaptureClaimUnverifiableError
from police_thief.domain.simultaneity import (
    DEFAULT_SIMULTANEITY_POLICY,
    SimultaneityPolicy,
    TurnMovement,
)
from police_thief.domain.state import LocalState

CLAIM_KIND_LANDED = "landed"
CLAIM_KIND_BARRIER_ON_THIEF = "barrier_on_thief"
CLAIM_KIND_NO_LEGAL_MOVE = "no_legal_move"
CLAIM_KINDS: frozenset[str] = frozenset(
    {CLAIM_KIND_LANDED, CLAIM_KIND_BARRIER_ON_THIEF, CLAIM_KIND_NO_LEGAL_MOVE}
)

_REASON_TO_KIND: dict[CaptureReason, str] = {
    CaptureReason.COP_LANDED_ON_THIEF: CLAIM_KIND_LANDED,
    CaptureReason.BARRIER_ON_THIEF: CLAIM_KIND_BARRIER_ON_THIEF,
    CaptureReason.THIEF_HAS_NO_LEGAL_MOVE: CLAIM_KIND_NO_LEGAL_MOVE,
}
_KIND_TO_REASON: dict[str, CaptureReason] = {v: k for k, v in _REASON_TO_KIND.items()}


def claim_kind_for_reason(reason: CaptureReason) -> str:
    return _REASON_TO_KIND[reason]


def reason_for_claim_kind(kind: str) -> CaptureReason:
    return _KIND_TO_REASON[kind]


def thief_truthful_verdict(
    claim_kind: str,
    thief_state: LocalState,
    config: SharedConfig,
    *,
    barrier_cell: Coordinate | None = None,
    movement: TurnMovement | None = None,
    policy: SimultaneityPolicy = DEFAULT_SIMULTANEITY_POLICY,
) -> CaptureVerdict:
    """What genuinely happened, from the thief's own true state.

    This is the *only* thing that makes a ``confirm``/``deny`` response
    truthful by construction rather than by promise.
    """
    if claim_kind == CLAIM_KIND_BARRIER_ON_THIEF:
        if barrier_cell is None:
            return CaptureVerdict.none()
        return evaluate_barrier_capture(barrier_cell, thief_state.position)

    if claim_kind == CLAIM_KIND_NO_LEGAL_MOVE:
        return evaluate_trapped_capture(thief_state, config)

    if claim_kind == CLAIM_KIND_LANDED:
        if movement is None:
            raise CaptureClaimUnverifiableError(
                "a 'landed' claim needs the cop's true resulting position, "
                "which this peer never legitimately has (E-8/E-9); supply "
                "'movement' explicitly or leave this to the offline replay"
            )
        return evaluate_movement_capture(movement, policy)

    raise ValueError(f"unknown claim_kind {claim_kind!r}")


def verdict_confirms_claim(verdict: CaptureVerdict, claim_kind: str) -> bool:
    """Does the thief's own truthful finding match what the cop claimed?

    Both the *fact* of capture and the *ground* must match -- a thief that
    was genuinely trapped is not confirming a ``landed`` claim.
    """
    if not verdict or verdict.reason is None:
        return False
    return claim_kind_for_reason(verdict.reason) == claim_kind
