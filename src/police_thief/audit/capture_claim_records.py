"""Audit-record payload shaping for capture_claim.

Hash-chained via the existing :mod:`police_thief.audit.writer` /
:mod:`police_thief.audit.chain` machinery -- called from
``peer/capture_claim_runtime.py``, not reimplemented here. This module only
shapes the free-form ``payload`` dict and, symmetrically, reads it back out
of a decoded log (used by ``replay/capture_claim_check.py``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from police_thief.audit.records import AuditEventType
from police_thief.protocol.capture_claim import CaptureClaim, CaptureClaimResponse


def claim_payload(claim: CaptureClaim, *, claimant_role: str) -> dict[str, Any]:
    return {**claim.to_payload(), "claimant_role": claimant_role}


def response_payload(response: CaptureClaimResponse, *, responder_role: str) -> dict[str, Any]:
    return {**response.to_payload(), "responder_role": responder_role}


def find_claim_records(
    records: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Every logged ``CAPTURE_CLAIM`` event, in log order."""
    kind = AuditEventType.CAPTURE_CLAIM.value
    return [r for r in records if r.get("event_type") == kind]


def find_response_records(
    records: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Every logged ``CAPTURE_CLAIM_RESPONSE`` event, in log order."""
    kind = AuditEventType.CAPTURE_CLAIM_RESPONSE.value
    return [r for r in records if r.get("event_type") == kind]
