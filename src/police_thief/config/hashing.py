"""SHA-256 hashing of the shared configuration.

``config_sha256`` is the PDF's own field name (Appendix B, PDF p. 127), not one
we coined. It is exchanged at the pre-match handshake; a mismatch means refusing
to play (E-11), because an identical config *is* an identical physics engine
(PDF p. 21: with no central server, both sides must agree the same transition
function, and it is encoded in the shared configuration file).

Scope note -- hashing versus signing
------------------------------------
The PDF requires the shared configuration to be **both** hashed and
cryptographically signed: "locked with a cryptographic signature" (PDF p. 126),
a consistent hash ``config_sha256`` (PDF p. 127), and "lock them
cryptographically" (Appendix F section 2, PDF p. 156).

**This module implements the hash only.** The signature depends on the
step-zero signing key, which the PDF refers to as "a pre-supplied key"
(PDF p. 56) without ever saying who supplies it, which algorithm, or how the
counterpart verifies it -- see OPEN_QUESTIONS.md Q-12, the one item still
requiring the lecturer's input. No key-distribution scheme is invented here.
When the answer arrives, signing lands behind this module's interface.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from police_thief.config.canonical import canonical_json_bytes
from police_thief.config.exceptions import ConfigHashMismatchError


def sha256_hex(payload: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


def config_sha256(shared_mapping: Mapping[str, Any]) -> str:
    """Return ``config_sha256`` for a shared configuration mapping.

    Computed over the canonical bytes of the *whole* shared document, including
    ``schema_version`` and ``agreed_between`` -- both peers load the same file,
    so the whole file is what must agree.

    The digest is independent of source whitespace and key order, and changes if
    any binding value changes. The private per-peer configuration is not an
    input and cannot affect it.
    """
    return sha256_hex(canonical_json_bytes(dict(shared_mapping)))


def verify_config_sha256(
    shared_mapping: Mapping[str, Any], expected: str
) -> str:
    """Check a shared configuration against an expected digest.

    Returns the computed digest when it matches; raises
    :class:`ConfigHashMismatchError` otherwise. Used at the handshake, where the
    correct response to a mismatch is to refuse to play (E-11).
    """
    computed = config_sha256(shared_mapping)
    if computed != expected.strip().lower():
        raise ConfigHashMismatchError(
            f"config_sha256 mismatch: computed {computed}, expected {expected}. "
            f"Refuse to play -- the two peers do not share the same physics."
        )
    return computed
