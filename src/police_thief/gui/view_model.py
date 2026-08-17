"""Read-only snapshot of what a peer may display.

This is the information boundary for the live GUI (E-8, E-9), and it is a
*type*, not a convention: :class:`LiveView` has no field for the opponent's
position, so a renderer cannot draw one and a leak cannot be introduced by
editing the drawing code. E-9 carries the heaviest sanction in the
specification -- disqualification of the project for an illegal advantage -- and
the interface is the most likely place to break it, because showing both agents
is exactly what a person watching would want.

The snapshot is built by :func:`snapshot`, which reads the orchestrator and
copies out only what is legal:

* own position, board size, public barriers (declared, so shared knowledge);
* the belief distribution -- a probability per cell, never a fact;
* the opponent's scent field, which is what this peer senses;
* protocol status: peer state, connection, commit/reveal phase, turn;
* the latest hint *received*, which the opponent chose to send us;
* operational errors.

Building a snapshot never mutates anything. The GUI is a reader.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

FORBIDDEN_VIEW_FIELDS: frozenset[str] = frozenset(
    {
        "opponent_position",
        "opponent_cell",
        "true_opponent_position",
        "thief_position",
        "cop_position",
        "police_position",
        "global_state",
        "full_board_state",
        "board_state",
        "ground_truth",
        "opponent_nonce",
        "nonce",
        "opponent_action",
        "pending_action",
        "sealed_record",
        "opponent_private_config",
    }
)
"""Names that must never appear on a live view.

Three families, all banned for the same reason -- anything here would either
hand this peer an illegal advantage (E-9) or expose material that must stay
sealed until the final reveal (E-18): the opponent's true position, unrevealed
action or nonce material, and replay-only omniscient state.
"""


@dataclass(frozen=True, slots=True)
class LiveView:
    """Everything the live GUI is allowed to show. Immutable."""

    role: str
    game_id: str
    grid_size: int
    origin_index: int

    own_position: tuple[int, int]
    barriers: tuple[tuple[int, int], ...]
    barriers_placed: int
    barriers_remaining: int

    belief: Mapping[tuple[int, int], float] = field(default_factory=dict)
    """Probability the opponent is in each cell. A distribution, not a location.

    Its peak is this peer's best guess and may simply be wrong -- which is the
    point, and why displaying it is legal where displaying a position is not.
    """

    scent: Mapping[tuple[int, int], float] = field(default_factory=dict)
    """The opponent's trail, as this peer senses it."""

    peer_state: str = "created"
    connection: str = "disconnected"
    phase: str = "idle"
    turn: int = 0
    turns_completed: int = 0

    opponent_name: str | None = None
    config_sha256: str = ""
    latest_hint: str = ""
    latest_hint_intent: str = ""
    """The intent the opponent *declared*. It may be a lie -- that is the game."""

    error: str | None = None
    final_status: str | None = None

    def belief_at(self, row: int, col: int) -> float:
        return self.belief.get((row, col), 0.0)

    def scent_at(self, row: int, col: int) -> float:
        return self.scent.get((row, col), 0.0)

    @property
    def belief_peak(self) -> tuple[int, int] | None:
        if not self.belief:
            return None
        return max(self.belief, key=lambda c: (self.belief[c], -c[0], -c[1]))

    def to_dict(self) -> dict[str, Any]:
        """Serialisable form, for tests and headless status output."""
        return {
            "role": self.role,
            "game_id": self.game_id,
            "grid_size": self.grid_size,
            "own_position": list(self.own_position),
            "barriers": [list(b) for b in self.barriers],
            "barriers_remaining": self.barriers_remaining,
            "peer_state": self.peer_state,
            "connection": self.connection,
            "phase": self.phase,
            "turn": self.turn,
            "turns_completed": self.turns_completed,
            "opponent_name": self.opponent_name,
            "config_sha256": self.config_sha256,
            "latest_hint": self.latest_hint,
            "latest_hint_intent": self.latest_hint_intent,
            "belief_cells": len(self.belief),
            "scent_cells": len(self.scent),
            "error": self.error,
            "final_status": self.final_status,
        }


def snapshot(orchestrator: Any) -> LiveView:
    """Copy the legal subset of a peer's state into a :class:`LiveView`.

    Reads; never writes. Every value is copied out, so a later mutation of the
    orchestrator cannot reach through a rendered frame.
    """
    state = orchestrator.state
    tracker = getattr(orchestrator, "tracker", None)
    shared = orchestrator.shared

    belief: dict[tuple[int, int], float] = {}
    scent: dict[tuple[int, int], float] = {}
    if tracker is not None:
        belief = {
            (c.row, c.col): p for c, p in tracker.belief.probabilities.items()
        }
        scent = {
            (c.row, c.col): v
            for c, v in tracker.opponent_scent.values.items()
            if v > 1e-6
        }

    crypto = getattr(orchestrator, "crypto", None)
    turns_completed = len(getattr(crypto, "completed_turns", ()) or ())
    phase = _phase_of(orchestrator)

    return LiveView(
        role=orchestrator.role.value,
        game_id=orchestrator.game_id,
        grid_size=state.board.size,
        origin_index=state.board.origin_index,
        own_position=state.position.as_tuple(),
        barriers=tuple(sorted(b.as_tuple() for b in state.board.barriers)),
        barriers_placed=state.barriers_placed,
        barriers_remaining=state.barriers_remaining(shared),
        belief=belief,
        scent=scent,
        peer_state=orchestrator.machine.state.value,
        connection=_connection_of(orchestrator),
        phase=phase,
        turn=state.turn,
        turns_completed=turns_completed,
        opponent_name=orchestrator.handshake.opponent_name,
        config_sha256=orchestrator.config_hash,
        latest_hint=getattr(orchestrator, "latest_opponent_hint", "") or "",
        latest_hint_intent=getattr(orchestrator, "latest_opponent_intent", "") or "",
        error=orchestrator.failure,
        final_status=getattr(orchestrator, "final_status", None),
    )


def _connection_of(orchestrator: Any) -> str:
    state = orchestrator.machine.state.value
    if state in ("ready", "turn_complete") or state.startswith(
        ("selecting", "local_", "waiting_for_opponent_", "both_", "reveal_",
         "verifying", "applying")
    ):
        return "connected"
    if state in ("disconnected", "error", "turn_failed"):
        return "lost"
    if state in ("created", "starting", "server_ready"):
        return "starting"
    return "connecting"


def _phase_of(orchestrator: Any) -> str:
    """Which commit-reveal phase we are in, in words a person can read."""
    state = orchestrator.machine.state.value
    readable = {
        "selecting_action": "choosing action",
        "local_action_sealed": "sealed (nonce held privately)",
        "waiting_for_opponent_commit": "committed — awaiting opponent",
        "both_commits_received": "both committed",
        "reveal_allowed": "reveal permitted",
        "local_reveal_sent": "revealed — awaiting opponent",
        "waiting_for_opponent_reveal": "awaiting opponent reveal",
        "verifying_reveal": "verifying",
        "both_reveals_verified": "verified",
        "applying_turn": "applying",
        "turn_complete": "turn complete",
        "turn_failed": "turn failed",
    }
    return readable.get(state, "idle")
