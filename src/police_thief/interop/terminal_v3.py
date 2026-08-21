"""The one last sealed record a reference-v3 side still owes once its
sub-game outcome is already decided -- mirrors the reference peer's own
``terminal_message()`` (``sparring/turnloop.py``): without it, a thief that
sees its own capture returns immediately and never delivers the concession,
so the cop -- which cannot see the board -- waits out its budget and
settles a sub-game it actually won as a timeout. Both sides then describe
the same game differently, which is the shape App. E rule 35 zeroes.

Free function operating on a :class:`~police_thief.interop.game_session.
GameSessionV3` rather than a method on it, for the same reason
:mod:`game_receive` is: keeps :mod:`game_session` under the 150-line limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from police_thief.interop.audit_adapter import seal_record
from police_thief.interop.scent_v3 import emit_v3
from police_thief.interop.wire import turn_message

if TYPE_CHECKING:
    from police_thief.interop.game_session import GameSessionV3


def terminal_message(session: GameSessionV3) -> dict[str, Any] | None:
    """A real ``STAY`` turn -- so the record chain and delivery ``step``
    counter both stay consistent, and the opponent's inbox actually applies
    it instead of absorbing a repeat -- carrying only a pending
    answer/concession and, only if THIS side itself crossed the survival
    threshold, a fresh survival claim. Returns ``None`` when there is
    nothing left to say (mirrors the reference: a side with nothing pending
    sends nothing rather than resealing empty state).
    """
    answer, session.pending_answer = session.pending_answer, None
    win_claim = {"type": "survival"} if session._self_survived else None
    session._self_survived = False
    if answer is None and win_claim is None:
        return None

    session.step += 1
    payload = {
        "step": session.step, "sub_game": session.sub_game_number,
        "role": session.role.value,
        "position": list(session.state.position.as_list()), "action": "STAY",
    }
    record = seal_record(payload)
    session.records.append(record)
    field_now = emit_v3(
        session.state.position.as_tuple(), session.scent_model.center_intensity,
        session.scent_model.window, session.board.size,
    )
    return turn_message(
        step=session.step, sender=session.role.value, hint="",
        smell_grid=field_now, commit=record["commit"], timestamp=session.clock_stamp(),
        barrier_placed=None, capture_claim=None,
        claim_response=answer, win_claim=win_claim,
    )
