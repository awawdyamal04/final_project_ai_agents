"""Receive-side handling for :class:`GameSessionV3`: structural validation,
the delivery contract, and adjudication from only what this side is
entitled to know (the cop learns of a capture solely from what the thief
*says*; the thief sees its own capture directly).

Free functions rather than methods on ``GameSessionV3`` so that file can
stay under 150 lines on its own; both are one cohesive unit conceptually.
"""

from __future__ import annotations

from typing import Any

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.transition import observe_barrier
from police_thief.interop.capture_v3 import answer_landed_claim, self_report_concession
from police_thief.interop.game_session import GameSessionV3
from police_thief.interop.turn_validate import validate_turn_message


def receive_turn(session: GameSessionV3, raw: Any) -> list[dict[str, Any]]:
    """Validate structurally, apply the delivery contract, then adjudicate
    every message now ready -- in order. Returns the messages actually
    applied (redeliveries and buffered-but-not-yet-ready arrivals are not
    included). Raises :class:`TurnValidationError`, :class:`Equivocation` or
    :class:`ProtocolViolation` -- always *before* any state change, per
    ``turn_message.json``'s own ``validate_before_applying`` rule.
    """
    validate_turn_message(raw)
    ready = session.inbox.offer(raw)
    for message in ready:
        _apply(session, message)
    return ready


def _apply(session: GameSessionV3, message: dict[str, Any]) -> None:
    barrier_placed = message.get("barrier_placed")
    conceded = False
    if barrier_placed is not None:
        cell = Coordinate(*barrier_placed)
        session.state = observe_barrier(session.state, cell)
        if session.role.value == "thief":
            concession = self_report_concession(
                session.state, session.config, barrier_just_placed=barrier_placed
            )
            if concession is not None:
                session.pending_answer = concession
                session.outcome = "capture"
                conceded = True

    session.absorb_scent(message.get("smell_grid") or {})
    session.last_hint = message.get("hint", "")

    # A cop's barrier and its capture_claim can ride the SAME message. If the
    # barrier just conceded the game (rule 46/47 -- a fact only the thief can
    # see), that concession must never be overwritten by the answer to the
    # claim that rides alongside it: the claim is a *guess* at our cell, and
    # a guess that missed (``caught=False``) would silently replace the true
    # ``caught=True`` concession with a false "not caught" -- leaving the
    # cop, which cannot see the board, waiting out its budget for a capture
    # its own barrier already produced (the live round-2 failure shape).
    claim = message.get("capture_claim")
    if claim is not None and session.role.value == "thief" and not conceded:
        answer = answer_landed_claim(claim, session.state)
        session.pending_answer = answer
        if answer and answer.get("caught"):
            session.outcome = "capture"

    response = message.get("claim_response")
    if response is not None and response.get("caught"):
        session.outcome = "capture"

    win_claim = message.get("win_claim")
    if win_claim and win_claim.get("type") == "survival":
        session.outcome = "survival"
