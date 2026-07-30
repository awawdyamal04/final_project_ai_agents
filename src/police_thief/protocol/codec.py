"""Wire encoder and decoder.

Delegates all serialisation to :mod:`police_thief.config.canonical`. There is
exactly one canonical-JSON implementation in this project, and this is not a
second one -- it is a caller. Two implementations would eventually disagree,
and the failure mode is a hash mismatch at audit costing both sides the match
(E-19).

No pickle, no ``eval``, no object hooks that construct arbitrary types. The
decoder accepts JSON and produces either a validated :class:`Envelope` or an
exception.
"""

from __future__ import annotations

import json
from typing import Any

from police_thief.config.canonical import canonical_json_bytes
from police_thief.config.exceptions import CanonicalSerialisationError
from police_thief.protocol.exceptions import (
    PayloadTooLargeError,
    ProtocolDecodeError,
)
from police_thief.protocol.messages import Envelope, envelope_from_wire

MAX_PAYLOAD_BYTES = 64 * 1024
"""Bounded message size.

64 KiB is far above anything the protocol legitimately sends -- the largest
Phase 2 message is a hello with a capability list, well under 1 KiB -- and far
below anything that threatens memory. An unbounded decoder is a
denial-of-service surface, and E-29 requires denial-of-service detectors
protecting network resources.

Not an Appendix F parameter: the PDF says nothing about message size, so this
is a project decision (DECISIONS.md D-29).
"""


def encode_envelope(envelope: Envelope) -> bytes:
    """Serialise to canonical JSON bytes, enforcing the size bound."""
    try:
        raw = canonical_json_bytes(envelope.to_wire())
    except CanonicalSerialisationError as exc:
        raise ProtocolDecodeError(f"envelope is not serialisable: {exc}") from exc

    if len(raw) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(
            f"encoded message is {len(raw)} bytes, over the "
            f"{MAX_PAYLOAD_BYTES}-byte limit"
        )
    return raw


def encode_envelope_text(envelope: Envelope) -> str:
    return encode_envelope(envelope).decode("utf-8")


def decode_envelope(raw: bytes | str) -> Envelope:
    """Decode and fully validate a wire message.

    Size is checked *before* parsing: an oversized message must be refused
    without being processed, which is the whole point of a bound.
    """
    if isinstance(raw, str):
        data = raw.encode("utf-8")
    elif isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    else:
        raise ProtocolDecodeError(
            f"expected bytes or str, got {type(raw).__name__}"
        )

    if len(data) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(
            f"message is {len(data)} bytes, over the "
            f"{MAX_PAYLOAD_BYTES}-byte limit"
        )

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolDecodeError(f"message is not valid UTF-8: {exc}") from exc

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolDecodeError(f"message is not valid JSON: {exc}") from exc

    return envelope_from_wire(parsed)


def decode_mapping(raw: Any) -> Envelope:
    """Validate an already-parsed mapping.

    FastMCP hands tool arguments over as Python objects, so a message arriving
    through a tool call has already been parsed by the transport. Re-encoding it
    only to decode it again would be wasted work; this path applies the same
    validation to the mapping directly.
    """
    return envelope_from_wire(raw)
