"""At-least-once delivery contract (SPEC section 7.1, PROMOTED).

Reimplemented from ``sparring/inbox.py``'s documented behaviour, not copied:
dedupe on the ``commit`` value (not ``(kind, step)``, which would silently
collapse a redelivery and a real equivocation together), a bounded reorder
window, and a below-``next``-and-never-played arrival treated as a discard
(anrbj666's 2026-08-04 finding -- letting it fall through to "buffer" left it
there forever and let two conformant receivers legitimately diverge on it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from police_thief.interop.exceptions import Equivocation, ProtocolViolation


def delivery_decision(played: dict[int, str], window: int, next_step: int, arrival: dict) -> str:
    """One inbound arrival's fate: ``absorb`` / ``equivocation`` / ``apply``
    / ``buffer`` / ``violation`` / ``discard``. See module docstring."""
    step, commit = arrival["step"], arrival["commit"]
    if step in played:
        return "absorb" if played[step] == commit else "equivocation"
    if step == next_step:
        return "apply"
    if step < next_step:
        return "discard"
    if step - next_step <= window:
        return "buffer"
    return "violation"


@dataclass
class Inbox:
    """Per-sub-game receive buffer for one side's TurnMessage chain.

    ``window`` is the negotiated (or configured) reorder tolerance; ``0``
    means *any* out-of-order arrival is a violation, which is a legitimate
    negotiated choice, not a bug (App. E rule 35: a self-inflicted protocol
    fault zeroes both teams equally, so a receiver's own strictness is at its
    own risk, not the sender's).
    """

    window: int = 4
    next_step: int = 1
    played: dict[int, str] = field(default_factory=dict)
    buffered: dict[int, dict[str, Any]] = field(default_factory=dict)

    def offer(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Feed one inbound message; return every message now ready to
        apply, in step order (the just-applied one plus anything it
        unblocks from the buffer)."""
        decision = delivery_decision(self.played, self.window, self.next_step, message)
        if decision == "absorb":
            return []
        if decision == "equivocation":
            raise Equivocation(
                f"step {message['step']}: commit {message['commit']!r} differs from "
                f"already-played {self.played[message['step']]!r}"
            )
        if decision == "violation":
            raise ProtocolViolation(
                f"step {message['step']} is outside the reorder window "
                f"(next={self.next_step}, window={self.window})"
            )
        if decision == "discard":
            return []
        if decision == "buffer":
            self.buffered[message["step"]] = message
            return []

        # "apply": drain this step and anything now contiguous behind it.
        ready = [message]
        self.played[message["step"]] = message["commit"]
        self.next_step += 1
        while self.next_step in self.buffered:
            nxt = self.buffered.pop(self.next_step)
            self.played[nxt["step"]] = nxt["commit"]
            self.next_step += 1
            ready.append(nxt)
        return ready


def deadline_decision(deadline_at: float, now: float) -> str:
    """"expired" or "waiting". One clock per *expected* message; tolerated
    traffic (an absorbed redelivery) never renews it -- the caller simply
    does not call this when nothing was expected."""
    return "expired" if now >= deadline_at else "waiting"
