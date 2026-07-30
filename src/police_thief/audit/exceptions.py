"""Audit-log errors."""

from __future__ import annotations


class AuditError(Exception):
    """Base class for audit-log failures."""


class AuditChainError(AuditError):
    """The hash chain is broken."""


class AuditRecordSchemaError(AuditChainError):
    """A record violates the closed schema."""


class AuditHashMismatchError(AuditChainError):
    """A recomputed hash does not match the one stored.

    Proof of modification. SHA-256 is sensitive to a single bit, so this is not
    a matter of degree (Ch. 5, PDF p. 55).
    """


class AuditChainBreakError(AuditChainError):
    """A record's ``previous_event_hash`` does not match its predecessor.

    Catches deletion, insertion and reordering: each of those leaves some
    record pointing at a hash that is no longer in front of it.
    """


class DuplicateAuditEventError(AuditChainError):
    """The same ``event_id`` appears twice."""


class AuditPrivacyError(AuditError):
    """An attempt to record forbidden content.

    Raised at write time rather than filtered, so a careless caller gets an
    exception instead of a leak in a file that later gets shared.
    """
