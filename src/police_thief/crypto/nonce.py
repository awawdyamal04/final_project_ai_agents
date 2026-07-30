"""Nonce generation and the local reuse guard.

Ch. 5 (PDF p. 50) defines the nonce and its two jobs: *"first, it guarantees
that even if an agent repeats exactly the same action, the resulting hash will
differ every time. Second, it defeats a dictionary attack -- an attempt by the
opponent to guess the sealed content by pre-hashing all the likely
possibilities. Without the nonce, the small move space would allow any
commitment to be cracked in a fraction of a second."*

That second reason sets the bar. The action space is tiny -- five moves plus a
handful of barrier cells -- so the nonce is the *only* thing standing between a
commitment and a lookup table. It must come from :mod:`secrets`, never
:mod:`random`, whose Mersenne Twister state is recoverable from its output.

Secrecy schedule (E-18, PDF p. 51): the nonce is created at commit time, kept
private through the reveal, and disclosed only at the final audit at the end of
the match. It never appears in a commit payload, never in a per-turn reveal,
and never in a log record before that final disclosure.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

NONCE_BYTES = 16
"""128 bits, matching the reference implementation's ``secrets.token_hex(16)``
(Ch. 5, PDF p. 52).

Not an Appendix F parameter -- the PDF fixes no nonce length -- so this is a
project decision (DECISIONS.md D-35). 128 bits is far beyond what the threat
needs: the attack it defeats is enumeration of a move space with tens of
elements, and any brute force over 2^128 is not a consideration.
"""

NONCE_HEX_LENGTH = NONCE_BYTES * 2


def generate_nonce() -> str:
    """Return a fresh cryptographic nonce as lowercase hex.

    ``secrets.token_hex`` draws from the OS entropy source and already emits
    lowercase; the explicit ``.lower()`` documents that the representation is
    part of the contract, since the nonce is later hashed and a case difference
    would change the digest.
    """
    return secrets.token_hex(NONCE_BYTES).lower()


def is_well_formed(nonce: str) -> bool:
    """Is this a syntactically valid nonce?"""
    return (
        isinstance(nonce, str)
        and len(nonce) == NONCE_HEX_LENGTH
        and all(c in "0123456789abcdef" for c in nonce)
    )


@dataclass
class NonceGuard:
    """Refuses to issue or accept a nonce this process has already used.

    A local guard, not a distributed one: it cannot see the opponent's nonces
    and does not try to. Its job is to catch *our own* bug -- a coordinator
    reusing a pending record across turns -- before that bug becomes a
    commitment we cannot honour.

    Collision from :func:`generate_nonce` is not a realistic failure mode at 128
    bits; this guard exists for the programming error, not the birthday
    paradox.
    """

    issued: set[str] = field(default_factory=set)

    def issue(self) -> str:
        """Generate and record a fresh nonce."""
        nonce = generate_nonce()
        while nonce in self.issued:  # pragma: no cover - 2^-128 per attempt
            nonce = generate_nonce()
        self.issued.add(nonce)
        return nonce

    def remember(self, nonce: str) -> None:
        """Record a nonce that was issued elsewhere."""
        self.issued.add(nonce)

    def has_used(self, nonce: str) -> bool:
        return nonce in self.issued

    def __len__(self) -> int:
        return len(self.issued)
