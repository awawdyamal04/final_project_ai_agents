"""``submit_audit`` (SPEC section 7.5, PROMOTED): reveal every sealed record
with its nonce, so the opponent can re-hash each one with its own
serializer. Recomputation uses the exact byte-level fix already shipped in
commit ``33db121``: :func:`pipe_nonce_commitment` -- the pipe-appended-nonce
form, not the book's ch.5 sealed-nonce form -- which is what makes a false
tamper detection from a serialization difference impossible here (the same
canonical serializer this project's own commit-reveal and config hashing
already use, see ``config/canonical.py``).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from police_thief.config.hashing import pipe_nonce_commitment


def seal_record(payload: dict[str, Any], nonce: str | None = None) -> dict[str, Any]:
    """One sealed step: ``{payload, nonce, commit}``. The commit is what
    rides the ``TurnMessage``; ``payload``/``nonce`` are withheld until
    ``submit_audit``."""
    nonce = nonce if nonce is not None else secrets.token_hex(16)
    return {
        "payload": payload,
        "nonce": nonce,
        "commit": pipe_nonce_commitment(payload, nonce),
    }


@dataclass(frozen=True)
class AuditResult:
    verified: bool
    mismatches: tuple[str, ...] = field(default_factory=tuple)

    @property
    def tampered(self) -> bool:
        return not self.verified and bool(self.mismatches)


def verify_audit(theirs: dict[str, Any], *, played: dict[int, str]) -> AuditResult:
    """Re-hash every revealed record and check it against what was actually
    received on the wire for that step during play.

    Two independent checks per record, both must pass:

    * **integrity** -- ``pipe_nonce_commitment(payload, nonce)`` reproduces
      the record's own declared ``commit``;
    * **binding** -- that same commit matches what this side actually
      received as that step's ``TurnMessage.commit`` (a record revealed here
      but never played, or played with a different commit, is exactly what
      commit-reveal exists to catch).
    """
    records = theirs.get("records")
    if not isinstance(records, list):
        return AuditResult(verified=False, mismatches=("`records` is missing or not a list",))

    mismatches: list[str] = []
    for record in records:
        step = record.get("payload", {}).get("step") if isinstance(record, dict) else None
        if not isinstance(record, dict) or not {"payload", "nonce", "commit"} <= set(record):
            mismatches.append(f"step {step}: record missing payload/nonce/commit")
            continue
        recomputed = pipe_nonce_commitment(record["payload"], record["nonce"])
        if recomputed != record["commit"]:
            mismatches.append(
                f"step {step}: declared commit {record['commit']!r} does not match "
                f"the revealed payload+nonce (recomputed {recomputed!r})"
            )
            continue
        seen = played.get(step)
        if seen is not None and seen != record["commit"]:
            mismatches.append(
                f"step {step}: revealed commit {record['commit']!r} differs from what "
                f"was actually played ({seen!r}) -- equivocation"
            )

    return AuditResult(verified=not mismatches, mismatches=tuple(mismatches))
