"""Protocol and transport errors.

Split into two families that callers treat very differently:

* :class:`ProtocolError` -- the message is wrong. **Never retry.** Sending the
  same malformed message again produces the same rejection and burns quota.
* :class:`TransportError` -- the message may have been fine but did not get
  through. **Retryable**, within bounds.

Getting that distinction wrong in either direction is expensive: retrying a
validation failure wastes the rate budget the Gatekeeper exists to protect, and
*not* retrying a dropped packet turns a blip into a technical loss.
"""

from __future__ import annotations


class PeerProtocolError(Exception):
    """Base class for everything in this module."""

    retryable: bool = False


# ----------------------------------------------------------------------
# Message-level -- never retryable
# ----------------------------------------------------------------------


class ProtocolError(PeerProtocolError):
    """The message itself is unacceptable."""

    retryable = False


class ProtocolDecodeError(ProtocolError):
    """The bytes are not decodable as a canonical-JSON envelope."""


class ProtocolValidationError(ProtocolError):
    """The envelope decoded but violates the schema."""


class UnsupportedSchemaVersionError(ProtocolValidationError):
    """The envelope schema version is not the one we speak."""


class UnsupportedProtocolVersionError(ProtocolValidationError):
    """The protocol major version is incompatible."""


class UnknownMessageTypeError(ProtocolValidationError):
    """The message type is not in the closed set."""


class PayloadTooLargeError(ProtocolValidationError):
    """The encoded message exceeds the bounded size.

    A bound is not paranoia: an unbounded decoder is a denial-of-service
    surface, and E-29 requires denial-of-service detectors protecting network
    resources.
    """


class WrongSenderRoleError(ProtocolValidationError):
    """The sender claims a role that is not our opponent's."""


class WrongReceiverRoleError(ProtocolValidationError):
    """The message is addressed to someone else."""


class WrongGameIdError(ProtocolValidationError):
    """The message belongs to a different match."""


class MissingCapabilityError(ProtocolValidationError):
    """The opponent does not advertise a capability we require."""


class StaleTurnError(ProtocolValidationError):
    """The message refers to a turn already past."""


class FutureTurnError(ProtocolValidationError):
    """The message refers to a turn we have not reached."""


class ConflictingDuplicateError(ProtocolValidationError):
    """A message id was reused with a different payload.

    This is the signature of an attempt to change a decision after the fact --
    exactly what commit-reveal exists to prevent (Ch. 5, PDF p. 49). Logged as
    evidence rather than merely refused.
    """


class DuplicateMessageError(ProtocolError):
    """A message id was seen before. Usually benign; the cached reply is
    returned instead of raising."""


class InvalidPeerStateError(ProtocolError):
    """The message is not legal in the peer's current state (E-5)."""


# ----------------------------------------------------------------------
# Transport-level -- retryable within bounds
# ----------------------------------------------------------------------


class TransportError(PeerProtocolError):
    """The message did not get through."""

    retryable = True


class PeerUnavailableError(TransportError):
    """The opponent could not be reached at all."""


class PeerTimeoutError(TransportError):
    """No response within ``response_timeout_sec`` (E-6).

    A missed deadline is a failure, not an invitation to wait longer
    (PDF p. 81).
    """


class InvalidResponseError(TransportError):
    """A response arrived but was not a well-formed envelope."""

    retryable = False


class RetryLimitExceededError(TransportError):
    """``max_retries`` attempts all failed. Never retried again."""

    retryable = False


# ----------------------------------------------------------------------
# Gatekeeper -- our own outbound limits (E-28, E-29)
# ----------------------------------------------------------------------


class GatekeeperError(PeerProtocolError):
    """Base class for our own admission control."""

    retryable = True


class RateLimitExceededError(GatekeeperError):
    """Sending now would exceed ``requests_per_minute``."""


class QueueCapacityExceededError(GatekeeperError):
    """``queue_depth`` in-flight or queued requests already."""


class ConcurrencyLimitExceededError(GatekeeperError):
    """``concurrent_requests`` already in flight."""
