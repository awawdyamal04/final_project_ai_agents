"""Step-zero declaration -- interface only, signing deliberately unimplemented.

Ch. 5 (PDF p. 56) requires a pre-match declaration of hardware, code version,
team, sub-game number and the GitHub commit hash actually played (E-24, E-53),
and says the whole specification is *"packed into a JSON string and
cryptographically signed using **a pre-supplied key**, so it cannot be forged
after the fact."*

**The PDF never says who supplies that key, which algorithm it uses, or how the
counterpart verifies it.** No Appendix F parameter covers it and no appendix
describes a distribution mechanism. That is OPEN_QUESTIONS.md Q-12, the one
item still requiring the lecturer's input.

So this module provides the *shape* and refuses to invent the substance:

* :class:`StepZeroSigner` -- the interface a real signer will implement.
* :class:`UnsignedStepZero` -- the shipped implementation, which **declines**.
* :class:`Sha256CommitmentSigner` -- a hash-only stand-in, honest about being
  a commitment and not a signature (DECISIONS.md D-8).

What is *not* done here, on purpose: no key is generated, no PKI is invented,
no self-signed certificate is minted, and a config hash is not passed off as a
signature. A fabricated mechanism would be worse than a missing one, because it
would look complete.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from police_thief.config.canonical import canonical_json_bytes
from police_thief.config.hashing import sha256_hex
from police_thief.crypto.exceptions import UnsignedStepZeroError

STEP_ZERO_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class StepZeroDeclaration:
    """The pre-match declaration (E-24, E-53).

    Content is fully specified by the PDF; only the *signing* is open.
    """

    game_id: str
    sub_game: int
    role: str
    group_name: str
    group_id: str
    code_version: str
    github_commit: str
    """E-53: the commit hash actually played. Code may change between matches,
    but every match must record which version competed."""

    hardware: Mapping[str, Any]
    llm: Mapping[str, Any]
    token_budget: int

    def to_mapping(self) -> dict[str, Any]:
        return {
            "v": STEP_ZERO_SCHEMA_VERSION,
            "game_id": self.game_id,
            "sub_game": self.sub_game,
            "role": self.role,
            "group_name": self.group_name,
            "group_id": self.group_id,
            "code_version": self.code_version,
            "github_commit": self.github_commit,
            "hardware": dict(self.hardware),
            "llm": dict(self.llm),
            "token_budget": self.token_budget,
        }

    def digest(self) -> str:
        """SHA-256 over the canonical declaration. Not a signature."""
        return sha256_hex(canonical_json_bytes(self.to_mapping()))


class StepZeroSigner(Protocol):
    """What a real signer will have to provide, once Q-12 is answered."""

    name: str
    available: bool

    def sign(self, declaration: StepZeroDeclaration) -> str: ...

    def verify(
        self, declaration: StepZeroDeclaration, signature: str
    ) -> bool: ...


@dataclass
class UnsignedStepZero:
    """The shipped default: declines to sign.

    Raising is the honest behaviour. Returning an empty string, or silently
    succeeding, would let the rest of the system behave as though E-24 were
    satisfied when it is not.
    """

    name: str = "unsigned"
    available: bool = False

    def sign(self, declaration: StepZeroDeclaration) -> str:
        raise UnsignedStepZeroError(
            "step-zero signing is not implemented: the PDF requires a "
            "'pre-supplied key' (Ch. 5, PDF p. 56) but never says who supplies "
            "it, which algorithm, or how it is verified. See OPEN_QUESTIONS.md "
            "Q-12 -- ask the lecturer before the first counting match. No key "
            "scheme has been invented here."
        )

    def verify(self, declaration: StepZeroDeclaration, signature: str) -> bool:
        raise UnsignedStepZeroError(
            "step-zero verification is not implemented; see Q-12"
        )


@dataclass
class Sha256CommitmentSigner:
    """Interim stand-in: a SHA-256 commitment over the declaration (D-8).

    Satisfies the *stated goal* -- the declaration "cannot be forged after the
    fact", because the digest is exchanged and locked at handshake time -- using
    machinery the project already mandates, and requiring no external secret.

    It is **not** a signature: it proves the declaration has not changed since
    it was published, not that a particular party authored it. Anyone can
    compute it. Named for what it is so nobody later mistakes it for what it is
    not.
    """

    name: str = "sha256-commitment"
    available: bool = True
    issued: list[str] = field(default_factory=list)

    def sign(self, declaration: StepZeroDeclaration) -> str:
        digest = declaration.digest()
        self.issued.append(digest)
        return digest

    def verify(self, declaration: StepZeroDeclaration, signature: str) -> bool:
        return declaration.digest() == signature
