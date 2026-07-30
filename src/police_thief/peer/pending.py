"""Buffer for messages that arrive one turn early.

The two peers act simultaneously and run at slightly different speeds, so one
routinely finishes turn N and sends its turn N+1 commit while the other is still
completing N. Nobody did anything wrong -- that is what "simultaneous" means --
but the receiver was rejecting it as a future turn, which failed the match from
about turn three onward.

The fix is to hold such a message rather than refuse it. It is buffered,
acknowledged, and replayed into the normal handler the moment the local turn
advances. Ordering is not weakened: the message is still not *processed* until
its turn is genuinely current, so a commit cannot be recorded early and a reveal
still cannot arrive before both commits exist.

What stays strict
-----------------
* **One turn of tolerance, no more.** Two turns ahead is rejected. A peer that
  far ahead is not racing us, it is running a different game.
* **Stale is still stale.** A message for a completed turn is refused.
* **Duplicates keep their semantics.** An exact retry of a buffered message
  returns the same acknowledgement; the same id with a different payload is a
  conflict and is refused, because reusing an id to change a decision is
  precisely what the commitment scheme exists to prevent.
* **Bounded.** ``queue_depth`` is the ceiling, and in practice the buffer holds
  at most a couple of messages -- one commit and one reveal for the next turn.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping

from police_thief.config.canonical import canonical_json_bytes
from police_thief.protocol.exceptions import ConflictingDuplicateError
from police_thief.protocol.messages import Envelope

MAX_TURNS_AHEAD = 1
"""How far ahead a peer may legitimately be.

One. Both peers take exactly one action per turn and neither may start turn N+2
before turn N+1 has completed, so anything further ahead is a protocol error
rather than a timing difference.
"""


@dataclass(frozen=True, slots=True)
class BufferedMessage:
    """A message held until its turn becomes current."""

    envelope: Envelope
    response: Mapping[str, Any]
    """The acknowledgement already returned to the sender.

    Sent at buffering time, not at processing time: the sender is waiting, and
    making it wait for our slower turn to finish would just move the timeout to
    the other side. Acknowledging receipt is honest -- we have the message and
    will act on it in order.
    """

    @property
    def turn(self) -> int:
        return self.envelope.turn_number or 0

    @property
    def key(self) -> tuple[int, str]:
        """Ordering key: turn first, then message type.

        Deterministic draining matters -- both peers must process a turn's
        messages in the same order or their logs diverge. ``commit`` sorts
        before ``reveal`` alphabetically, which is also the protocol order.
        """
        return (self.turn, self.envelope.message_type.value)


class PendingTurnBuffer:
    """Holds next-turn messages until the local turn catches up."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("buffer capacity must be at least 1")
        self._capacity = capacity
        self._items: OrderedDict[str, BufferedMessage] = OrderedDict()
        self.buffered = 0
        self.drained = 0
        self.overflows = 0

    def __len__(self) -> int:
        return len(self._items)

    @property
    def capacity(self) -> int:
        return self._capacity

    def __contains__(self, message_id: str) -> bool:
        return message_id in self._items

    def lookup(
        self, message_id: str, payload: Mapping[str, Any]
    ) -> BufferedMessage | None:
        """Return an already-buffered message for an exact retry.

        Raises :class:`ConflictingDuplicateError` if the id comes back with a
        different payload. Comparison is by canonical bytes, so a peer whose
        JSON orders keys differently is not accused of tampering.
        """
        held = self._items.get(message_id)
        if held is None:
            return None
        if _fingerprint(held.envelope.payload) != _fingerprint(payload):
            raise ConflictingDuplicateError(
                f"message id {message_id!r} is buffered with a different "
                f"payload; reusing an id to change a decision is what the "
                f"commitment scheme exists to prevent"
            )
        return held

    def add(self, envelope: Envelope, response: Mapping[str, Any]) -> BufferedMessage:
        """Buffer a message. Raises if the buffer is full."""
        if len(self._items) >= self._capacity:
            self.overflows += 1
            raise BufferOverflowError(
                f"pending buffer is full ({self._capacity}); refusing to hold "
                f"turn {envelope.turn_number} {envelope.message_type.value}"
            )
        held = BufferedMessage(envelope=envelope, response=dict(response))
        self._items[envelope.message_id] = held
        self.buffered += 1
        return held

    def take_for_turn(self, turn: int) -> list[BufferedMessage]:
        """Remove and return everything held for ``turn``, in a fixed order."""
        ready = [m for m in self._items.values() if m.turn == turn]
        ready.sort(key=lambda m: m.key)
        for message in ready:
            self._items.pop(message.envelope.message_id, None)
        self.drained += len(ready)
        return ready

    def clear(self) -> int:
        """Drop everything. Used on shutdown and on a failed turn.

        A buffered message belongs to a turn that will now never run, so keeping
        it would mean replaying it into a game that has moved on.
        """
        count = len(self._items)
        self._items.clear()
        return count

    def turns_held(self) -> tuple[int, ...]:
        return tuple(sorted({m.turn for m in self._items.values()}))


class BufferOverflowError(Exception):
    """Too many messages held for future turns.

    Retryable from the sender's point of view: we are behind, not broken.
    """

    retryable = True


def _fingerprint(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(dict(payload))
