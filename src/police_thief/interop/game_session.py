"""One sub-game under ``wire_shape: reference-v3``: seal, push, receive,
adjudicate.

Reuses this project's already-tested domain layer wholesale (``LocalState``,
``apply_action``, ``BeliefMap``, ``CopStrategy``/``RiskThiefStrategy``) and
adds only the reference-v3-specific glue: the outbound ``smell_grid``
(``subtractive_chebyshev_v1``, :mod:`scent_v3`), the sealed record/commit
shape (:mod:`audit_adapter`), and capture-claim self-verification
(:mod:`capture_v3`). Receive-side handling lives in :mod:`game_receive`, and
the post-outcome closing message lives in :mod:`terminal_v3`; both operate
on this class rather than subclassing it, to keep every file under the
150-line limit.

**Emission choice** (not interop-critical -- ``vectors/pheromone.json``
itself calls the wire ``smell_grid`` a self-test): each outbound turn
carries the fresh radial field around this peer's *current* cell, computed
by the byte-verified :func:`emit_v3`, rather than an accumulating decayed
trail -- how a sender chooses to accumulate across steps is not part of the
promoted wire contract.

**Turn order**: the thief moves first under reference-v3 -- the reference
implementation's own observed behaviour (not settled by the book).
``opens`` tells a caller whether this side must send turn 1 unprompted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from police_thief.config.models import SharedConfig
from police_thief.domain.actions import PlaceBarrier
from police_thief.domain.belief import BeliefMap
from police_thief.domain.board import Board
from police_thief.domain.enums import Role
from police_thief.domain.scent import ScentModel
from police_thief.domain.state import LocalState
from police_thief.domain.terminal import evaluate_survival
from police_thief.domain.transition import apply_action
from police_thief.interop.audit_adapter import seal_record
from police_thief.interop.delivery import Inbox
from police_thief.interop.scent_v3 import emit_v3, scent_field_from_wire
from police_thief.interop.terminal_v3 import terminal_message
from police_thief.interop.wire import turn_message
from police_thief.strategy.base import LocalView
from police_thief.strategy.heuristics import CopStrategy
from police_thief.strategy.thief_risk import RiskThiefStrategy


@dataclass
class GameSessionV3:
    role: Role
    config: SharedConfig
    sub_game_number: int
    clock_stamp: Callable[[], str]
    strategy: Any = None
    step: int = 0
    state: LocalState = field(init=False)
    belief: BeliefMap = field(init=False)
    board: Board = field(init=False)
    scent_model: ScentModel = field(init=False)
    inbox: Inbox = field(default_factory=Inbox)
    records: list[dict[str, Any]] = field(default_factory=list)
    last_hint: str = ""
    last_claim: list[int] | None = None
    pending_answer: dict[str, Any] | None = None
    outcome: str | None = None  # "capture" | "survival" | None
    _self_survived: bool = field(default=False, init=False, repr=False)
    _opponent_scent: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.state = LocalState.initial(self.role, self.config)
        self.board = self.state.board
        self.belief = BeliefMap.uniform(self.board)
        self.scent_model = ScentModel.from_config(self.config)
        if self.strategy is None:
            self.strategy = CopStrategy() if self.role is Role.POLICE else RiskThiefStrategy()

    @property
    def opens(self) -> bool:
        return self.role is Role.THIEF

    def absorb_scent(self, opponent_field: dict[str, float]) -> None:
        self._opponent_scent = scent_field_from_wire(opponent_field, self.scent_model, self.board)
        self.belief.update_from_scent(self._opponent_scent)

    def take_turn(self) -> dict[str, Any]:
        """Compute and seal this side's next half-turn.

        Once ``outcome`` is already decided (a self-detected rule-46/47
        capture, or a survival claim already sent), this stops choosing new
        actions and instead reseals a terminal ``STAY`` record -- exactly
        the reference peer's own split between a regular turn and
        ``terminal_message()`` (``sparring/turnloop.py``). Continuing to
        move and reseal *new* game state after the sub-game is locally over
        is not itself wrong by the wire's rules, but it was hiding the one
        thing that IS load-bearing: a pending ``claim_response`` must go out
        on its own, focused, undelayed message, not folded behind a full
        strategy evaluation that a slow opponent connection can stall.
        """
        if self.outcome is not None:
            return self._terminal_message()

        self.step += 1
        opponent_scent = self._opponent_scent or scent_field_from_wire(
            {}, self.scent_model, self.board
        )
        view = LocalView(state=self.state, config=self.config, belief=self.belief,
                         opponent_scent=opponent_scent)
        action = self.strategy.choose(view)
        result = apply_action(self.state, action, self.config)
        self.state = result.state

        barrier_placed = list(action.cell.as_list()) if isinstance(action, PlaceBarrier) else None
        claim = list(self.state.position.as_list()) if self.role is Role.POLICE else None
        if claim is not None:
            self.last_claim = claim

        payload = {
            "step": self.step, "sub_game": self.sub_game_number, "role": self.role.value,
            "position": list(self.state.position.as_list()), "action": str(action),
        }
        record = seal_record(payload)
        self.records.append(record)

        win_claim = None
        if self._survived():
            win_claim = {"type": "survival"}
            self.outcome = "survival"
            self._self_survived = True
        field_now = emit_v3(
            self.state.position.as_tuple(), self.scent_model.center_intensity,
            self.scent_model.window, self.board.size,
        )
        answer, self.pending_answer = self.pending_answer, None
        return turn_message(
            step=self.step, sender=self.role.value, hint=self.last_hint,
            smell_grid=field_now, commit=record["commit"], timestamp=self.clock_stamp(),
            barrier_placed=barrier_placed, capture_claim=claim,
            claim_response=answer, win_claim=win_claim,
        )

    def _survived(self) -> bool:
        return self.role is Role.THIEF and evaluate_survival(self.step, self.config) is not None

    def _terminal_message(self) -> dict[str, Any] | None:
        return terminal_message(self)
