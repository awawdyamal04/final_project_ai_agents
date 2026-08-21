"""Errors raised by the reference-v3 adapter.

Kept separate from ``protocol/exceptions.py`` on purpose: those exceptions
describe *this project's own* wire, and reusing them here would blur which
protocol a failure belongs to when both surfaces run in the same process.
"""

from __future__ import annotations


class ReferenceV3Error(Exception):
    """Base for every reference-v3 adapter failure."""


class Refused(ReferenceV3Error):
    """A negotiation refusal, with the kit's own stable SPAR-Nxx style code
    so an operator can grep for it exactly as the reference peer does."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class TurnValidationError(ReferenceV3Error):
    """An inbound ``TurnMessage`` fails the promoted structural schema
    (SPEC section 7.5) -- decided *before* any state change (turn_message.json
    ``validate_before_applying``)."""


class Equivocation(ReferenceV3Error):
    """A second, different commit arrived for a step already played."""


class ProtocolViolation(ReferenceV3Error):
    """An inbound arrival is outside the negotiated reorder window, or is
    otherwise structurally illegal (e.g. a barrier declared by the thief)."""
