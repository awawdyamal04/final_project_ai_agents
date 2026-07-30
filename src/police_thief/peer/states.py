"""The peer lifecycle state machine (E-4, E-5).

A transition not in the table is rejected immediately and **does not change the
state** -- so a rejected event leaves the peer exactly where it was. Ch. 8
(PDF p. 80) gives the reasoning: an illegal transition should raise at once
rather than leave the system in an undefined state, turning a silent
in-game freeze into a visible development-time error.

Phase 3 adds the cryptographic turn states. Their ordering is the protocol's
safety property, not a convenience: the machine physically cannot reach
``REVEAL_ALLOWED`` without passing through ``BOTH_COMMITS_RECEIVED``, so
"reveal only once both sides have fixed their moves" (Ch. 5, PDF p. 51) is
enforced by the transition table rather than by a check someone could forget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from police_thief.protocol.exceptions import InvalidPeerStateError


class PeerState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    SERVER_READY = "server_ready"
    CONNECTING = "connecting"
    HELLO_EXCHANGE = "hello_exchange"
    CONFIG_EXCHANGE = "config_exchange"
    CONFIG_VERIFIED = "config_verified"
    READY_WAIT = "ready_wait"
    READY = "ready"

    # --- Phase 3: the cryptographic turn --------------------------------
    SELECTING_ACTION = "selecting_action"
    LOCAL_ACTION_SEALED = "local_action_sealed"
    WAITING_FOR_OPPONENT_COMMIT = "waiting_for_opponent_commit"
    BOTH_COMMITS_RECEIVED = "both_commits_received"
    REVEAL_ALLOWED = "reveal_allowed"
    LOCAL_REVEAL_SENT = "local_reveal_sent"
    WAITING_FOR_OPPONENT_REVEAL = "waiting_for_opponent_reveal"
    VERIFYING_REVEAL = "verifying_reveal"
    BOTH_REVEALS_VERIFIED = "both_reveals_verified"
    APPLYING_TURN = "applying_turn"
    TURN_COMPLETE = "turn_complete"
    TURN_FAILED = "turn_failed"

    FINISHING = "finishing"
    FINISHED = "finished"
    ERROR = "error"
    DISCONNECTED = "disconnected"


TERMINAL_STATES: frozenset[PeerState] = frozenset(
    {PeerState.FINISHED, PeerState.ERROR}
)
"""Once here, nothing further happens. ``DISCONNECTED`` is deliberately not
terminal: a lost peer still needs a controlled wind-down, and Ch. 8 (PDF p. 79)
describes exactly that -- a controlled exit rather than an eternal wait."""


TRANSITIONS: dict[PeerState, frozenset[PeerState]] = {
    PeerState.CREATED: frozenset({PeerState.STARTING, PeerState.ERROR}),
    PeerState.STARTING: frozenset({PeerState.SERVER_READY, PeerState.ERROR}),
    PeerState.SERVER_READY: frozenset(
        {PeerState.CONNECTING, PeerState.FINISHING, PeerState.ERROR}
    ),
    PeerState.CONNECTING: frozenset(
        {
            PeerState.HELLO_EXCHANGE,
            PeerState.DISCONNECTED,
            PeerState.FINISHING,
            PeerState.ERROR,
        }
    ),
    PeerState.HELLO_EXCHANGE: frozenset(
        {
            PeerState.CONFIG_EXCHANGE,
            PeerState.DISCONNECTED,
            PeerState.FINISHING,
            PeerState.ERROR,
        }
    ),
    PeerState.CONFIG_EXCHANGE: frozenset(
        {
            PeerState.CONFIG_VERIFIED,
            PeerState.DISCONNECTED,
            PeerState.FINISHING,
            PeerState.ERROR,
        }
    ),
    PeerState.CONFIG_VERIFIED: frozenset(
        {
            PeerState.READY_WAIT,
            PeerState.DISCONNECTED,
            PeerState.FINISHING,
            PeerState.ERROR,
        }
    ),
    PeerState.READY_WAIT: frozenset(
        {
            PeerState.READY,
            PeerState.DISCONNECTED,
            PeerState.FINISHING,
            PeerState.ERROR,
        }
    ),
    PeerState.READY: frozenset(
        {
            PeerState.SELECTING_ACTION,
            PeerState.FINISHING,
            PeerState.DISCONNECTED,
            PeerState.ERROR,
        }
    ),
    # --- the cryptographic turn, in mandatory order --------------------
    PeerState.SELECTING_ACTION: frozenset(
        {PeerState.LOCAL_ACTION_SEALED, PeerState.TURN_FAILED, PeerState.ERROR}
    ),
    PeerState.LOCAL_ACTION_SEALED: frozenset(
        {
            PeerState.WAITING_FOR_OPPONENT_COMMIT,
            PeerState.TURN_FAILED,
            PeerState.ERROR,
        }
    ),
    PeerState.WAITING_FOR_OPPONENT_COMMIT: frozenset(
        {
            PeerState.BOTH_COMMITS_RECEIVED,
            PeerState.TURN_FAILED,
            PeerState.DISCONNECTED,
            PeerState.ERROR,
        }
    ),
    # There is no edge from anywhere else into REVEAL_ALLOWED. That absence is
    # what enforces "no reveal before both commitments exist" (PDF p. 51).
    PeerState.BOTH_COMMITS_RECEIVED: frozenset(
        {PeerState.REVEAL_ALLOWED, PeerState.TURN_FAILED, PeerState.ERROR}
    ),
    PeerState.REVEAL_ALLOWED: frozenset(
        {PeerState.LOCAL_REVEAL_SENT, PeerState.TURN_FAILED, PeerState.ERROR}
    ),
    PeerState.LOCAL_REVEAL_SENT: frozenset(
        {
            PeerState.WAITING_FOR_OPPONENT_REVEAL,
            PeerState.TURN_FAILED,
            PeerState.ERROR,
        }
    ),
    PeerState.WAITING_FOR_OPPONENT_REVEAL: frozenset(
        {
            PeerState.VERIFYING_REVEAL,
            PeerState.TURN_FAILED,
            PeerState.DISCONNECTED,
            PeerState.ERROR,
        }
    ),
    PeerState.VERIFYING_REVEAL: frozenset(
        {PeerState.BOTH_REVEALS_VERIFIED, PeerState.TURN_FAILED, PeerState.ERROR}
    ),
    # Nothing reaches APPLYING_TURN except through verification.
    PeerState.BOTH_REVEALS_VERIFIED: frozenset(
        {PeerState.APPLYING_TURN, PeerState.TURN_FAILED, PeerState.ERROR}
    ),
    PeerState.APPLYING_TURN: frozenset(
        {PeerState.TURN_COMPLETE, PeerState.TURN_FAILED, PeerState.ERROR}
    ),
    PeerState.TURN_COMPLETE: frozenset(
        {
            PeerState.SELECTING_ACTION,  # next turn
            PeerState.FINISHING,
            PeerState.DISCONNECTED,
            PeerState.ERROR,
        }
    ),
    PeerState.TURN_FAILED: frozenset({PeerState.FINISHING, PeerState.ERROR}),
    PeerState.FINISHING: frozenset({PeerState.FINISHED, PeerState.ERROR}),
    PeerState.DISCONNECTED: frozenset({PeerState.FINISHING, PeerState.ERROR}),
    PeerState.FINISHED: frozenset(),
    PeerState.ERROR: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Transition:
    """One recorded state change."""

    source: PeerState
    target: PeerState
    reason: str
    at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "from": self.source.value,
            "to": self.target.value,
            "reason": self.reason,
            "at": round(self.at, 6),
        }


@dataclass
class PeerStateMachine:
    """Holds the peer's lifecycle state.

    The state is private and can only be changed through :meth:`transition`.
    Nothing outside this class assigns it, which is what makes "no direct state
    assignment" a property rather than a convention.
    """

    now: Callable[[], float]
    _state: PeerState = field(default=PeerState.CREATED, init=False)
    _history: list[Transition] = field(default_factory=list, init=False)

    @property
    def state(self) -> PeerState:
        return self._state

    @property
    def history(self) -> tuple[Transition, ...]:
        return tuple(self._history)

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    def can_transition_to(self, target: PeerState) -> bool:
        return target in TRANSITIONS[self._state]

    def transition(self, target: PeerState, reason: str = "") -> Transition:
        """Move to ``target``, or raise without changing anything."""
        if self._state is target and target not in TERMINAL_STATES:
            # Idempotent re-entry: re-driving the same transition (a retried
            # handshake step, say) must not be an error, and must not append a
            # spurious history entry.
            return Transition(self._state, target, "idempotent", self.now())

        if not self.can_transition_to(target):
            raise InvalidPeerStateError(
                f"illegal transition {self._state.value} -> {target.value}; "
                f"legal targets: "
                f"{sorted(s.value for s in TRANSITIONS[self._state])}"
            )

        record = Transition(self._state, target, reason, self.now())
        self._state = target
        self._history.append(record)
        return record

    def require(self, *allowed: PeerState) -> None:
        """Assert the peer is in one of ``allowed``."""
        if self._state not in allowed:
            raise InvalidPeerStateError(
                f"peer is {self._state.value}; this operation requires one of "
                f"{sorted(s.value for s in allowed)}"
            )
