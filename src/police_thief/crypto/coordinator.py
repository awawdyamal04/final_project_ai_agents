"""The commit-reveal coordinator.

Owns the cryptographic material for one turn and nothing else. It does not
choose the action, does not check board legality, does not apply movement, does
not score, and does not know where the opponent is. Those belong to strategy,
the domain, and an adjudicator respectively; keeping them out is what lets this
component be reasoned about on its own.

The four phases, in the PDF's order (Ch. 5, PDF pp. 50-51)
==========================================================
1. **Commit** -- seal the action with a fresh nonce, send *only* the digest.
2. **Acknowledge** -- the opponent confirms it is locked. This *"prevents the
   sender retreating from its commitment, and at the same time guarantees the
   reveal happens only once both sides have already fixed their moves."*
3. **Reveal** -- send the action and the verbal sentence. **The nonce stays
   hidden**: *"to prevent premature reverse-engineering of the signatures."*
4. **Final reveal / audit** -- *"only at the end of the whole game are all
   Nonce values revealed, for full mutual audit."*

A consequence worth stating plainly, because it shapes the whole design: **an
in-turn reveal cannot be hash-verified.** Without the nonce there is nothing to
recompute. What a peer verifies during the turn is *binding* -- game, sub-game,
turn, role, prior commitment, structural validity. The commitment itself is
verified at the final audit, and that is where tampering is caught (E-19).
Building it the other way round would require shipping the nonce early and
breaking E-18.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from police_thief.crypto.exceptions import (
    CommitAlreadyExistsError,
    CommitmentMismatchError,
    ConflictingCommitError,
    ConflictingRevealError,
    FutureTurnMessageError,
    InvalidRevealError,
    MissingCommitError,
    RevealNotAllowedError,
    SealedRecordValidationError,
    StaleTurnMessageError,
)
from police_thief.crypto.nonce import NonceGuard
from police_thief.crypto.sealed import (
    SEALED_SCHEMA_VERSION,
    SealedRecord,
    commitment_for_mapping,
    validate_sealed_mapping,
)
from police_thief.domain.actions import Action
from police_thief.domain.enums import Role
from police_thief.protocol.action_codec import decode_action


@dataclass
class TurnCrypto:
    """The cryptographic material for one turn.

    ``local_record`` holds the nonce and is never serialised outward except by
    :meth:`reveal_payload` (which strips it) and the final audit.
    """

    turn: int
    local_record: SealedRecord | None = None
    local_commitment: str | None = None
    opponent_commitment: str | None = None
    local_revealed: bool = False
    opponent_reveal: dict[str, Any] | None = None

    @property
    def both_committed(self) -> bool:
        return self.local_commitment is not None and self.opponent_commitment is not None

    @property
    def complete(self) -> bool:
        return self.local_revealed and self.opponent_reveal is not None


@dataclass
class CommitRevealCoordinator:
    """Drives one peer's side of the cryptographic turn."""

    game_id: str
    role: Role
    sub_game: int = 1
    nonces: NonceGuard = field(default_factory=NonceGuard)
    current: TurnCrypto | None = None
    completed_turns: dict[int, TurnCrypto] = field(default_factory=dict)
    audit_trail: list[SealedRecord] = field(default_factory=list)
    """Our own sealed records, kept privately until the final reveal."""

    @property
    def opponent_role(self) -> Role:
        return self.role.opponent

    # ------------------------------------------------------------------
    # Turn lifecycle
    # ------------------------------------------------------------------

    def begin_turn(self, turn: int) -> TurnCrypto:
        """Open a fresh turn, refusing to reopen an old one."""
        if turn in self.completed_turns:
            raise StaleTurnMessageError(
                f"turn {turn} is already complete and cannot be reopened"
            )
        if self.current is not None and self.current.turn != turn:
            raise FutureTurnMessageError(
                f"turn {self.current.turn} is still in progress; "
                f"cannot begin turn {turn}"
            )
        if self.current is None:
            self.current = TurnCrypto(turn=turn)
        return self.current

    def _require_turn(self, turn: int) -> TurnCrypto:
        if self.current is None:
            raise MissingCommitError(f"no turn in progress; got turn {turn}")
        if turn < self.current.turn or turn in self.completed_turns:
            raise StaleTurnMessageError(
                f"turn {turn} is behind the current turn {self.current.turn}"
            )
        if turn > self.current.turn:
            raise FutureTurnMessageError(
                f"turn {turn} is ahead of the current turn {self.current.turn}"
            )
        return self.current

    # ------------------------------------------------------------------
    # 1. Commit
    # ------------------------------------------------------------------

    def seal(
        self,
        *,
        turn: int,
        action: Action,
        hint: str,
        intent: str,
        state_hash: str,
    ) -> str:
        """Seal an action and return the commitment digest.

        The nonce is created here and never leaves this object until the final
        audit. The digest is all that goes on the wire.
        """
        crypto = self.begin_turn(turn)
        if crypto.local_commitment is not None:
            raise CommitAlreadyExistsError(
                f"already committed for turn {turn}; a second commitment would "
                f"be a change of decision after the fact"
            )

        nonce = self.nonces.issue()
        record = SealedRecord(
            game_id=self.game_id,
            sub_game=self.sub_game,
            turn=turn,
            role=self.role,
            state=state_hash,
            action=action,
            hint=hint,
            intent=intent,
            nonce=nonce,
        )
        crypto.local_record = record
        crypto.local_commitment = record.commitment()
        return crypto.local_commitment

    def commit_payload(self, turn: int) -> dict[str, Any]:
        """The wire payload for COMMIT: the digest and nothing else.

        Deliberately minimal. Any field describing the action -- its kind, its
        target, even its length -- would narrow the opponent's search over a
        move space small enough to enumerate.
        """
        crypto = self._require_turn(turn)
        if crypto.local_commitment is None:
            raise MissingCommitError(f"nothing sealed for turn {turn}")
        return {
            "commitment": crypto.local_commitment,
            "commitment_schema": SEALED_SCHEMA_VERSION,
        }

    def record_opponent_commit(self, turn: int, commitment: str) -> bool:
        """Record the opponent's commitment. Returns ``True`` if it was new.

        An identical repeat is idempotent -- retries are normal. A *different*
        commitment for the same turn is an attempt to change a locked decision
        and fails the turn.
        """
        crypto = self._require_turn(turn)
        if not _is_digest(commitment):
            raise InvalidRevealError(
                f"commitment must be 64 lowercase hex characters, "
                f"got {commitment!r}"
            )

        if crypto.opponent_commitment is None:
            crypto.opponent_commitment = commitment
            return True
        if crypto.opponent_commitment != commitment:
            raise ConflictingCommitError(
                f"opponent already committed {crypto.opponent_commitment[:12]}… "
                f"for turn {turn} and now sent a different commitment; a "
                f"commitment cannot be changed once made"
            )
        return False

    # ------------------------------------------------------------------
    # 2/3. Reveal
    # ------------------------------------------------------------------

    def reveal_allowed(self, turn: int) -> bool:
        crypto = self.current
        return crypto is not None and crypto.turn == turn and crypto.both_committed

    def reveal_payload(self, turn: int) -> dict[str, Any]:
        """The wire payload for REVEAL: action and hint, **no nonce**.

        Refuses before both commitments exist. Revealing early would hand the
        opponent a free look at our move while its own was still changeable --
        the exact asymmetry the acknowledge step exists to prevent.
        """
        crypto = self._require_turn(turn)
        if not crypto.both_committed:
            raise RevealNotAllowedError(
                f"cannot reveal turn {turn} before both commitments exist "
                f"(local={crypto.local_commitment is not None}, "
                f"opponent={crypto.opponent_commitment is not None})"
            )
        if crypto.local_record is None:  # pragma: no cover - defensive
            raise MissingCommitError(f"nothing sealed for turn {turn}")

        crypto.local_revealed = True
        payload = {"sealed": crypto.local_record.to_reveal_mapping()}
        assert "nonce" not in payload["sealed"], "E-18: nonce must stay hidden"
        return payload

    def accept_opponent_reveal(
        self, turn: int, sealed: Mapping[str, Any]
    ) -> Action:
        """Validate an opponent reveal and return its action.

        Checks *binding*, not the hash: without the nonce there is nothing to
        recompute. Verified here are the schema, the game/sub-game/turn/role
        this reveal claims, the existence of a prior commitment, and the action's
        structural validity. The commitment itself is checked at
        :meth:`verify_final_reveal`.
        """
        crypto = self._require_turn(turn)

        if crypto.opponent_commitment is None:
            raise MissingCommitError(
                f"opponent revealed turn {turn} without ever committing; "
                f"a reveal with no commitment proves nothing"
            )
        if not crypto.both_committed:
            raise RevealNotAllowedError(
                f"opponent revealed turn {turn} before both commitments existed"
            )

        validate_sealed_mapping(sealed, require_nonce=False)

        if sealed["game_id"] != self.game_id:
            raise InvalidRevealError(
                f"reveal claims game {sealed['game_id']!r}, "
                f"this peer is playing {self.game_id!r}"
            )
        if sealed["sub_game"] != self.sub_game:
            raise InvalidRevealError(
                f"reveal claims sub-game {sealed['sub_game']}, "
                f"this peer is playing {self.sub_game}"
            )
        if sealed["turn"] != turn:
            raise InvalidRevealError(
                f"reveal body claims turn {sealed['turn']} but arrived as "
                f"turn {turn}"
            )
        if sealed["role"] != self.opponent_role.value:
            raise InvalidRevealError(
                f"reveal claims role {sealed['role']!r}; this peer's opponent "
                f"is {self.opponent_role.value!r}"
            )

        if crypto.opponent_reveal is not None:
            if crypto.opponent_reveal != dict(sealed):
                raise ConflictingRevealError(
                    f"opponent already revealed turn {turn} with different "
                    f"content; a reveal cannot be retracted"
                )
            return decode_action(sealed["action"])

        crypto.opponent_reveal = dict(sealed)
        return decode_action(sealed["action"])

    # ------------------------------------------------------------------
    # 4. Final reveal and audit
    # ------------------------------------------------------------------

    def finish_turn(self, turn: int) -> TurnCrypto:
        """Close the turn, archiving its material for the final audit.

        The local record moves to the audit trail: it still holds the nonce,
        which is needed at the end of the match and must not be discarded --
        without it we cannot prove our own honesty.
        """
        crypto = self._require_turn(turn)
        if not crypto.complete:
            raise RevealNotAllowedError(
                f"turn {turn} is not complete (local_revealed="
                f"{crypto.local_revealed}, opponent_reveal="
                f"{crypto.opponent_reveal is not None})"
            )
        if crypto.local_record is not None:
            self.audit_trail.append(crypto.local_record)
        self.completed_turns[turn] = crypto
        self.current = None
        return crypto

    def abandon_turn(self, reason: str) -> int | None:
        """Discard an unfinished turn without leaking its nonce.

        Called on timeout or shutdown. The pending record is dropped entirely --
        an abandoned turn's nonce is never logged, never reported and never
        reused, because the commitment it belonged to will never be honoured.
        The nonce stays in the guard so it can never be issued again.
        """
        crypto, self.current = self.current, None
        if crypto is None:
            return None
        if crypto.local_record is not None:
            self.nonces.remember(crypto.local_record.nonce)
        return crypto.turn

    def final_reveal_payload(self) -> dict[str, Any]:
        """All our sealed records with nonces, for the end-of-match audit.

        This is the only place a nonce leaves the coordinator (E-18: *"only at
        the end of the whole game"*).
        """
        return {
            "records": [r.with_nonce_disclosed() for r in self.audit_trail]
        }

    def verify_final_reveal(
        self, records: list[Mapping[str, Any]]
    ) -> list[str]:
        """Recompute the opponent's commitments. Returns the verified turns.

        Ch. 5 (PDF p. 55): each side re-hashes the opponent's revealed data and
        compares against the signature declared at commit time. *"Any mismatch
        unambiguously proves tampering occurred"* -- and E-19 makes that a
        technical loss with a score of zero.
        """
        verified: list[str] = []
        for raw in records:
            try:
                validate_sealed_mapping(raw, require_nonce=True)
            except SealedRecordValidationError as exc:
                raise CommitmentMismatchError(
                    f"final reveal contains an invalid sealed record: {exc}"
                ) from exc

            turn = raw["turn"]
            crypto = self.completed_turns.get(turn)
            if crypto is None or crypto.opponent_commitment is None:
                raise MissingCommitError(
                    f"final reveal covers turn {turn}, for which no opponent "
                    f"commitment was ever recorded"
                )

            if raw["role"] != self.opponent_role.value:
                raise CommitmentMismatchError(
                    f"turn {turn}: final reveal claims role {raw['role']!r}"
                )

            if crypto.opponent_reveal is not None:
                without_nonce = {k: v for k, v in raw.items() if k != "nonce"}
                if without_nonce != crypto.opponent_reveal:
                    raise CommitmentMismatchError(
                        f"turn {turn}: the final reveal disagrees with what was "
                        f"revealed during the turn -- the action or hint was "
                        f"changed after the fact"
                    )

            recomputed = commitment_for_mapping(raw)
            if not _constant_time_equal(recomputed, crypto.opponent_commitment):
                raise CommitmentMismatchError(
                    f"turn {turn}: recomputed commitment "
                    f"{recomputed[:12]}… does not match the declared "
                    f"{crypto.opponent_commitment[:12]}…; SHA-256 is sensitive "
                    f"to a single bit, so this is proof of tampering, not doubt"
                )
            verified.append(f"turn {turn}")
        return verified


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _constant_time_equal(left: str, right: str) -> bool:
    """Timing-safe comparison of two digests.

    Overkill for a public commitment -- both values are already known to the
    opponent -- but the habit is worth keeping where the module's job is
    comparing secrets against claims.
    """
    import hmac

    return hmac.compare_digest(left, right)
