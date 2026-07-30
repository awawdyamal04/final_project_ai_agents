"""The sealed action record and its commitment.

PDF basis for the field set
===========================
Ch. 5 (PDF p. 50) gives the formula and names four components, and PDF p. 51
defines each. Quoting the definitions (translated):

* ``H_commit`` -- *"the commitment signature. A 256-bit string produced by
  SHA-256. It is the move's fingerprint; it is sent to the opponent but reveals
  nothing about its content."*
* ``State`` -- *"the board state. The snapshot on which the move is based,
  binding the commitment to a specific game step. Practical meaning: prevents
  reuse of an old commitment in a new context."*
* ``Move`` -- *"the physical action. The chosen move (movement, barrier
  placement and so on). This is the core that is being locked against change."*
* ``Intent`` -- *"the intent flag. A value stating whether the accompanying
  verbal hint is truthful (truth) or deceptive (lie). Practical meaning:
  obliges the agent to declare its sincerity in advance, so it cannot claim
  afterwards that it lied 'on purpose'."*
* ``Nonce`` -- *"a cryptographic random string... guarantees hash uniqueness and
  defeats a dictionary attack."*

The same page adds that the record actually sealed is **richer** than those
four: it *"also includes the verbal hint, the intent classification, the step
number and the role"*, and the sample code's comment adds ``sub_game``. And it
fixes the serialisation: *"canonical JSON (sorted keys, fixed separators) so
BOTH peers hash byte-identical input"*.

So the semantic field set is mandatory; the **key spelling is not prescribed
anywhere** and is a negotiated project decision (DECISIONS.md D-4, D-34). The
schema below is versioned so it can be renegotiated without ambiguity.

What is deliberately absent
---------------------------
No timestamp (the PDF requires none, and two clocks would break byte-identity),
no private configuration, no opponent position, no full board state. ``state``
is a *hash* of the committing peer's own pre-move local state, not the state
itself -- it binds the commitment to a position without disclosing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from police_thief.config.canonical import canonical_json_bytes
from police_thief.config.hashing import sha256_hex
from police_thief.crypto.exceptions import SealedRecordValidationError
from police_thief.crypto.nonce import is_well_formed
from police_thief.domain.actions import Action
from police_thief.domain.enums import Role
from police_thief.protocol.action_codec import decode_action, encode_action

SEALED_SCHEMA_VERSION = "1.0"
"""Versioned so the key spelling can be renegotiated explicitly."""

GENESIS_STATE_HASH = "0" * 64

INTENT_TRUTH = "truth"
INTENT_LIE = "lie"
VALID_INTENTS = frozenset({INTENT_TRUTH, INTENT_LIE})

SEALED_KEYS: frozenset[str] = frozenset(
    {
        "v",
        "game_id",
        "sub_game",
        "turn",
        "role",
        "state",
        "action",
        "hint",
        "intent",
        "nonce",
    }
)
"""The closed key set. Anything else is a validation error, in either
direction -- an unexpected key is as fatal as a missing one, because both
change the bytes and therefore the digest."""


@dataclass(frozen=True, slots=True)
class SealedRecord:
    """The immutable record whose SHA-256 digest is the commitment.

    Frozen, and the nonce is a field: an object whose sealed content could be
    edited after the digest was published would make the commitment meaningless.
    """

    game_id: str
    sub_game: int
    turn: int
    role: Role
    state: str
    """SHA-256 of the committing peer's own pre-move local state.

    A hash rather than the state itself. It binds the commitment to a specific
    position -- *"prevents reuse of an old commitment in a new context"* --
    without putting a position on the wire.
    """

    action: Action
    hint: str
    intent: str
    nonce: str
    v: str = SEALED_SCHEMA_VERSION

    # ------------------------------------------------------------------
    # Canonical form
    # ------------------------------------------------------------------

    def to_sealed_mapping(self) -> dict[str, Any]:
        """The exact mapping that gets hashed.

        Key spelling here *is* the protocol: canonical serialisation makes
        ``sub_game`` and ``subGame`` different commitments, so both peers must
        agree this schema before playing.
        """
        return {
            "v": self.v,
            "game_id": self.game_id,
            "sub_game": self.sub_game,
            "turn": self.turn,
            "role": self.role.value,
            "state": self.state,
            "action": encode_action(self.action),
            "hint": self.hint,
            "intent": self.intent,
            "nonce": self.nonce,
        }

    def commitment(self) -> str:
        """``SHA256(canonical_json_bytes(sealed_mapping))``, lowercase hex."""
        return sha256_hex(canonical_json_bytes(self.to_sealed_mapping()))

    # ------------------------------------------------------------------
    # The public half -- everything except the nonce
    # ------------------------------------------------------------------

    def to_reveal_mapping(self) -> dict[str, Any]:
        """What the per-turn reveal may carry.

        **Excludes the nonce**, per E-18 and Ch. 5 (PDF p. 51): *"The agent
        sends the opponent the action and the verbal sentence. The Nonce
        remains hidden at this stage, to prevent premature reverse-engineering
        of the signatures."*
        """
        mapping = self.to_sealed_mapping()
        del mapping["nonce"]
        return mapping

    def with_nonce_disclosed(self) -> dict[str, Any]:
        """The full record, for the final audit only (Ch. 5, PDF p. 51)."""
        return self.to_sealed_mapping()


# ----------------------------------------------------------------------
# Validation and reconstruction
# ----------------------------------------------------------------------


def validate_sealed_mapping(
    raw: Mapping[str, Any], *, require_nonce: bool = True
) -> None:
    """Check a mapping against the closed sealed schema."""
    if not isinstance(raw, dict):
        raise SealedRecordValidationError(
            f"sealed record must be an object, got {type(raw).__name__}"
        )

    expected = set(SEALED_KEYS) if require_nonce else set(SEALED_KEYS) - {"nonce"}

    for unknown in sorted(set(raw) - expected):
        raise SealedRecordValidationError(
            f"unknown sealed field {unknown!r}; the schema is closed because "
            f"any extra key changes the bytes and therefore the commitment"
        )
    for missing in sorted(expected - set(raw)):
        raise SealedRecordValidationError(f"missing sealed field {missing!r}")

    if raw["v"] != SEALED_SCHEMA_VERSION:
        raise SealedRecordValidationError(
            f"unsupported sealed schema version {raw['v']!r}; "
            f"this peer speaks {SEALED_SCHEMA_VERSION}"
        )

    for key in ("game_id", "state", "hint"):
        if not isinstance(raw[key], str):
            raise SealedRecordValidationError(
                f"{key} must be a string, got {type(raw[key]).__name__}"
            )
    if not raw["game_id"]:
        raise SealedRecordValidationError("game_id must not be empty")

    for key in ("sub_game", "turn"):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SealedRecordValidationError(
                f"{key} must be a non-negative integer, got {value!r}"
            )

    try:
        Role(raw["role"])
    except ValueError as exc:
        raise SealedRecordValidationError(
            f"role must be one of {sorted(r.value for r in Role)}, "
            f"got {raw['role']!r}"
        ) from exc

    if raw["intent"] not in VALID_INTENTS:
        raise SealedRecordValidationError(
            f"intent must be one of {sorted(VALID_INTENTS)}, "
            f"got {raw['intent']!r}"
        )

    # Structural validity only. Board legality needs a board and belongs to the
    # domain; the receiving peer enforces the physics separately (PDF p. 38).
    decode_action(raw["action"])

    if require_nonce and not is_well_formed(raw["nonce"]):
        raise SealedRecordValidationError(
            "nonce must be 32 lowercase hex characters"
        )


def sealed_record_from_mapping(raw: Mapping[str, Any]) -> SealedRecord:
    """Rebuild a :class:`SealedRecord` from a full mapping, nonce included."""
    validate_sealed_mapping(raw, require_nonce=True)
    return SealedRecord(
        v=raw["v"],
        game_id=raw["game_id"],
        sub_game=raw["sub_game"],
        turn=raw["turn"],
        role=Role(raw["role"]),
        state=raw["state"],
        action=decode_action(raw["action"]),
        hint=raw["hint"],
        intent=raw["intent"],
        nonce=raw["nonce"],
    )


def commitment_for_mapping(raw: Mapping[str, Any]) -> str:
    """Recompute a commitment from a full sealed mapping.

    Used at the final audit: the opponent's revealed fields plus its disclosed
    nonce are re-hashed and compared against what it committed.
    """
    validate_sealed_mapping(raw, require_nonce=True)
    return sha256_hex(canonical_json_bytes(dict(raw)))


def local_state_hash(state_mapping: Mapping[str, Any]) -> str:
    """Hash a peer's own local state, for the ``state`` binding field."""
    return sha256_hex(canonical_json_bytes(dict(state_mapping)))
