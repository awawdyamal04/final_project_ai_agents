"""Wire protocol: message schemas, codec, and the action wire form.

Deliberately free of transport. Nothing here imports FastMCP, and nothing here
imports game rules, scoring or strategy. The protocol package knows how to
describe and validate a message; it does not know how to send one or what a
move means.

That separation is asserted by ``tests/peer/test_information_boundary.py``.
"""

from police_thief.protocol.codec import (
    MAX_PAYLOAD_BYTES,
    decode_envelope,
    encode_envelope,
)
from police_thief.protocol.messages import (
    Envelope,
    MessageType,
    new_envelope,
)
from police_thief.protocol.versions import (
    MANDATORY_CAPABILITIES,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    SOFTWARE_VERSION,
    SUPPORTED_CAPABILITIES,
    is_protocol_compatible,
)

__all__ = [
    "MANDATORY_CAPABILITIES",
    "MAX_PAYLOAD_BYTES",
    "PROTOCOL_VERSION",
    "SCHEMA_VERSION",
    "SOFTWARE_VERSION",
    "SUPPORTED_CAPABILITIES",
    "Envelope",
    "MessageType",
    "decode_envelope",
    "encode_envelope",
    "is_protocol_compatible",
    "new_envelope",
]
