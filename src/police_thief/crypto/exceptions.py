"""Cryptographic turn errors.

Every one of these is non-retryable: a commitment mismatch or a reveal out of
order is a statement about the *content* of the exchange, and resending it
unchanged produces the same answer. Retrying would only spend the rate budget
the Gatekeeper exists to protect.
"""

from __future__ import annotations

from police_thief.protocol.exceptions import ProtocolError


class CryptoError(ProtocolError):
    """Base class for the cryptographic turn protocol."""

    retryable = False


# ----------------------------------------------------------------------
# Sealed record and nonce
# ----------------------------------------------------------------------


class SealedRecordValidationError(CryptoError):
    """A sealed record violates its closed schema."""


class NonceReuseError(CryptoError):
    """A nonce was used for a second commitment.

    Reuse destroys the scheme's binding property: two commitments sharing a
    nonce leak the relationship between their contents, and the whole point of
    a fresh nonce per commitment (Ch. 5, PDF p. 50) is that an identical action
    hashes differently every time.
    """


# ----------------------------------------------------------------------
# Commit phase
# ----------------------------------------------------------------------


class CommitmentError(CryptoError):
    """Base class for commitment failures."""


class CommitAlreadyExistsError(CommitmentError):
    """A commitment already exists for this role and turn."""


class ConflictingCommitError(CommitmentError):
    """A second, *different* commitment arrived for the same role and turn.

    This is an attempt to change a decision after making it -- precisely what
    commit-reveal exists to prevent (Ch. 5, PDF p. 49). The turn fails and the
    attempt is recorded as evidence.
    """


class MissingCommitError(CommitmentError):
    """A reveal arrived with no prior commitment to check it against."""


# ----------------------------------------------------------------------
# Reveal phase
# ----------------------------------------------------------------------


class RevealNotAllowedError(CryptoError):
    """A reveal was attempted before both commitments existed.

    The acknowledgement step exists to guarantee "the reveal happens only once
    both sides have already fixed their moves" (Ch. 5, PDF p. 51). Revealing
    early would hand the opponent a free look.
    """


class InvalidRevealError(CryptoError):
    """A reveal is malformed or does not bind to its commitment's context."""


class ConflictingRevealError(InvalidRevealError):
    """A second, different reveal arrived for the same role and turn."""


class CommitmentMismatchError(CryptoError):
    """A recomputed commitment does not equal the one declared.

    Detected at the final audit, when the nonces are disclosed. Ch. 5
    (PDF p. 55): any mismatch proves tampering unambiguously -- SHA-256 is
    sensitive to a single bit, so "there is no room for interpretation or
    statistical doubt". The consequence is a technical loss (E-19).
    """


class CryptoTurnTimeoutError(CryptoError):
    """A turn deadline expired while waiting for the opponent."""

    retryable = False


class TurnSequenceError(CryptoError):
    """A crypto message arrived for the wrong turn."""


class StaleTurnMessageError(TurnSequenceError):
    """The message refers to a turn already completed."""


class FutureTurnMessageError(TurnSequenceError):
    """The message refers to a turn not yet begun."""


# ----------------------------------------------------------------------
# Step zero -- deliberately unimplemented
# ----------------------------------------------------------------------


class UnsignedStepZeroError(CryptoError):
    """Step-zero signing was requested but no signer is configured.

    The PDF requires the step-zero declaration to be signed "with a pre-supplied
    key" (Ch. 5, PDF p. 56) but never says who supplies it, which algorithm, or
    how the counterpart verifies it. See OPEN_QUESTIONS.md Q-12. No key scheme
    is invented here.
    """
