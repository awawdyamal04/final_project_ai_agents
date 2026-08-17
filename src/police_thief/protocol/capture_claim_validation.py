"""Validation for ``CAPTURE_CLAIM`` / ``CAPTURE_CLAIM_RESPONSE`` envelopes.

Split out of :mod:`police_thief.protocol.capture_claim` purely to stay under
the 150-line lecturer limit -- same feature, same schema, just the role/
freshness/malformed-payload checks instead of the dataclasses.

Role checks reuse the existing ``WrongSenderRoleError``/
``WrongReceiverRoleError``; staleness reuses ``StaleTurnError``/
``FutureTurnError`` (``protocol/exceptions.py``) rather than inventing new
exception types for a feature-specific case of an already-generic problem.
"""

from __future__ import annotations

from police_thief.domain.enums import Role
from police_thief.protocol.capture_claim import (
    CLAIM_KINDS,
    VERDICTS,
    CaptureClaim,
    CaptureClaimResponse,
)
from police_thief.protocol.exceptions import (
    FutureTurnError,
    ProtocolValidationError,
    StaleTurnError,
    WrongReceiverRoleError,
    WrongSenderRoleError,
)


def validate_claim_envelope(envelope) -> CaptureClaim:
    """Structural + role validation for an inbound ``CAPTURE_CLAIM``."""
    if envelope.sender_role is not Role.POLICE:
        raise WrongSenderRoleError(
            f"CAPTURE_CLAIM must be sent by the cop; got "
            f"{envelope.sender_role.value!r} -- the thief cannot be the "
            f"mandatory initiator (Correction 1)"
        )
    if envelope.receiver_role is not Role.THIEF:
        raise WrongReceiverRoleError("CAPTURE_CLAIM must be addressed to the thief")
    if envelope.turn_number is None:
        raise ProtocolValidationError("CAPTURE_CLAIM must carry a turn_number")

    payload = envelope.payload
    claim_kind = payload.get("claim_kind")
    if claim_kind not in CLAIM_KINDS:
        raise ProtocolValidationError(
            f"claim_kind must be one of {sorted(CLAIM_KINDS)}, got {claim_kind!r}"
        )
    claim_id = payload.get("claim_id")
    if not isinstance(claim_id, str) or not claim_id:
        raise ProtocolValidationError("claim_id must be a non-empty string")

    return CaptureClaim(
        claim_id=claim_id,
        sub_game=payload["sub_game"],
        turn=envelope.turn_number,
        claim_kind=claim_kind,
        commitment=payload["commitment"],
    )


def validate_response_envelope(envelope) -> CaptureClaimResponse:
    """Structural + role validation for an inbound ``CAPTURE_CLAIM_RESPONSE``."""
    if envelope.sender_role is not Role.THIEF:
        raise WrongSenderRoleError(
            f"CAPTURE_CLAIM_RESPONSE must be sent by the thief; "
            f"got {envelope.sender_role.value!r}"
        )
    if envelope.receiver_role is not Role.POLICE:
        raise WrongReceiverRoleError("CAPTURE_CLAIM_RESPONSE must be addressed to the cop")
    if envelope.turn_number is None:
        raise ProtocolValidationError("CAPTURE_CLAIM_RESPONSE must carry a turn_number")

    payload = envelope.payload
    verdict = payload.get("verdict")
    if verdict not in VERDICTS:
        raise ProtocolValidationError(
            f"verdict must be one of {sorted(VERDICTS)}, got {verdict!r}"
        )
    claim_id = payload.get("claim_id")
    if not isinstance(claim_id, str) or not claim_id:
        raise ProtocolValidationError("claim_id must be a non-empty string")

    return CaptureClaimResponse(
        claim_id=claim_id,
        sub_game=payload["sub_game"],
        turn=envelope.turn_number,
        verdict=verdict,
        commitment=payload["commitment"],
    )


def validate_claim_freshness(claim_turn: int, latest_completed_turn: int) -> None:
    """A claim must concern the turn just completed -- not an old one (a
    replayed stale claim) and not one that has not happened yet."""
    if claim_turn < latest_completed_turn:
        raise StaleTurnError(
            f"capture claim references turn {claim_turn}, but turn "
            f"{latest_completed_turn} is already the latest completed turn"
        )
    if claim_turn > latest_completed_turn:
        raise FutureTurnError(
            f"capture claim references turn {claim_turn}, but only "
            f"{latest_completed_turn} turn(s) have been completed"
        )
