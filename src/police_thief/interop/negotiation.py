"""The reference-v3 pre-game gate (SPEC section 4, 7, 7.2, 7.3).

Reuses this project's own ``terms_signature``/``game_uid``/``game_id``
(``protocol/interop_ids.py``, already byte-verified against the kit's
vectors in ``tests/interop``) rather than re-deriving them. Only the
decision tables below (lock/pairing/uid refusal) are new, and they are
small, generic, and independently reasoned from SPEC section 7's one stated
rule: **omission never refuses, in either direction** -- the unmodified
reference peer declares none of these fields, and a guard that fail-fasts on
silence forfeits the game to itself.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.interop.decisions import lock_decision, pairing_decision
from police_thief.interop.exceptions import Refused
from police_thief.interop.wire import terms_from_config
from police_thief.protocol.interop_ids import game_id, game_uid, terms_signature

LOCK_FAMILIES: tuple[str, ...] = ("scent_model", "wire_shape", "info_mode", "smell_binding")


@dataclass(frozen=True)
class Agreed:
    game_id: str
    game_uid: str
    opponent_group: str
    opponent_role: str | None
    terms: dict[str, Any]


@dataclass
class Greeting:
    """This side's outbound negotiate payload, held for verification."""

    terms: dict[str, Any]
    nonce: str
    signature: str
    group_id: str
    role: str | None = None
    sub_game_number: int | None = None
    locks: dict[str, str] = field(default_factory=dict)
    declared_game_uid: str | None = None


def build_greeting(
    config: SharedConfig,
    *,
    group_id: str,
    role: str | None = None,
    sub_game_number: int | None = None,
    locks: dict[str, str] | None = None,
    opponent_group: str | None = None,
) -> Greeting:
    """``opponent_group``, once known (kit's own rule -- SPEC section 7.3):
    from sub-game 2 onward the same derived ``game_uid`` is declared on
    every greeting for the rest of the series. Sub-game 1 omits it -- the
    opponent identity is not yet pinned -- and omission never refuses."""
    terms = terms_from_config(config)
    nonce = secrets.token_hex(16)
    declared_uid = game_uid(terms, group_id, opponent_group) if opponent_group else None
    return Greeting(
        terms=terms,
        nonce=nonce,
        signature=terms_signature(terms, nonce),
        group_id=group_id,
        role=role,
        sub_game_number=sub_game_number,
        locks=dict(locks or {}),
        declared_game_uid=declared_uid,
    )


def to_wire(greeting: Greeting) -> dict[str, Any]:
    out: dict[str, Any] = {
        "terms": greeting.terms,
        "nonce": greeting.nonce,
        "signature": greeting.signature,
        "group_id": greeting.group_id,
    }
    if greeting.role is not None:
        out["role"] = greeting.role
    if greeting.sub_game_number is not None:
        out["sub_game_number"] = greeting.sub_game_number
    if greeting.declared_game_uid is not None:
        out["game_uid"] = greeting.declared_game_uid
    for family in LOCK_FAMILIES:
        value = greeting.locks.get(family)
        if value is not None:
            out[f"{family}_sha256"] = value
    return out


def verify_greeting(ours: Greeting, raw: Any) -> Agreed:
    """Check an inbound greeting, or raise :class:`Refused` with a
    diagnosis -- mirrors ``sparring/negotiate.py``'s ``verify_peer`` logic,
    reimplemented against this project's own primitives."""
    if not isinstance(raw, dict):
        raise Refused("SPAR-N00", f"greeting is {type(raw).__name__}, not an object")

    terms = raw.get("terms")
    if terms is None:
        raise Refused("SPAR-N01", "opponent greeting carries no `terms` at all")
    if not isinstance(terms, dict):
        raise Refused("SPAR-N02", f"`terms` is {type(terms).__name__}, not an object")
    missing = sorted(set(ours.terms) - set(terms))
    if missing:
        raise Refused("SPAR-N02", f"opponent terms are incomplete; missing {missing}")
    if terms != ours.terms:
        keys = sorted(set(ours.terms) | set(terms))
        diff = [k for k in keys if ours.terms.get(k) != terms.get(k)]
        raise Refused("SPAR-N03", f"opponent terms do not value-equal ours: {diff}")

    nonce, signature = raw.get("nonce"), raw.get("signature")
    if not nonce or not signature:
        raise Refused("SPAR-N04", "greeting carries no nonce/signature pair to verify")
    if terms_signature(terms, nonce) != signature:
        raise Refused("SPAR-N04", "the terms signature does not verify")

    for family in LOCK_FAMILIES:
        key = f"{family}_sha256"
        if lock_decision(ours.locks.get(family), raw.get(key)) == "refuse":
            raise Refused("SPAR-N05", f"{family} lock mismatch")

    decision = pairing_decision(ours.sub_game_number, ours.role, raw)
    if decision == "refuse:sub_game":
        raise Refused("SPAR-N06", "sub-game mismatch")
    if decision == "refuse:role":
        raise Refused("SPAR-N07", f"role collision: both peers declared {ours.role!r}")

    opponent = raw.get("group_id") or (raw.get("identity") or {}).get("group_id")
    if not opponent:
        raise Refused("SPAR-N08", "greeting names no group_id, so no game_id can be derived")

    derived_uid = game_uid(terms, ours.group_id, opponent)
    if lock_decision(derived_uid, raw.get("game_uid")) == "refuse":
        raise Refused("SPAR-N10", f"game_uid mismatch: we derive {derived_uid}")

    return Agreed(
        game_id=game_id(ours.group_id, opponent),
        game_uid=derived_uid,
        opponent_group=opponent,
        opponent_role=raw.get("role"),
        terms=terms,
    )
