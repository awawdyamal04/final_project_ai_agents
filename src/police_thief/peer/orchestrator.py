"""The peer orchestrator: single gateway to all sub-systems (E-3).

Ch. 8 (PDF p. 78) defines the role precisely: a central component that
initialises connections, drives the decision module, coordinates between
components and talks to the log managers -- but *"contains no decision logic or
low-level communication of its own. Its job is to coordinate, not to execute."*

So this class owns the lifecycle and the state machine, and delegates
everything else. It has no FastMCP parsing (that is
:mod:`police_thief.peer.server`), no game rules (that is the domain), and no
strategy (Phase 3).

Everything is injected -- transport, clock, id generator, event sink, config,
state machine -- because a peer that constructs its own dependencies cannot be
tested without a network, and an untestable handshake is one that gets debugged
during a league match.

What it must never do
---------------------
Store the opponent's true position, act as a referee, decide strategy, or
bypass ``LocalState``. It holds a ``LocalState`` for its own role and never
receives one for the other. Asserted by
``tests/peer/test_information_boundary.py::test_orchestrator_has_no_global_state_field``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field  # noqa: F401
from typing import Any

from police_thief.audit.records import AuditEventType
from police_thief.audit.writer import AuditLog
from police_thief.config.hashing import config_sha256
from police_thief.config.models import PrivateConfig, SharedConfig
from police_thief.crypto.coordinator import CommitRevealCoordinator
from police_thief.crypto.exceptions import (
    CommitmentMismatchError,
    CryptoTurnTimeoutError,
    FutureTurnMessageError,
)
from police_thief.crypto.sealed import local_state_hash
from police_thief.domain.actions import Action, PlaceBarrier
from police_thief.domain.enums import Role
from police_thief.domain.exceptions import DomainError
from police_thief.domain.simultaneity import (
    BLOCKED_MOVE_BECOMES_STAY,
    DEFAULT_SIMULTANEITY_POLICY,
)
from police_thief.domain.state import LocalState
from police_thief.domain.transition import apply_action, observe_barrier
from police_thief.peer.client import PeerClient
from police_thief.peer.clock import Clock, SystemClock
from police_thief.peer.deadline import RetryPolicy, Watchdog
from police_thief.peer.events import EventSink, NullEventSink
from police_thief.peer.gatekeeper import Gatekeeper, GatekeeperLimits
from police_thief.peer.pending import (
    MAX_TURNS_AHEAD,
    BufferOverflowError,
    PendingTurnBuffer,
)
from police_thief.peer.registry import MessageRegistry
from police_thief.peer.states import PeerState, PeerStateMachine
from police_thief.protocol.action_codec import decode_action, encode_action
from police_thief.protocol.exceptions import (
    ConflictingDuplicateError,
    InvalidPeerStateError,
    MissingCapabilityError,
    WrongGameIdError,
    WrongReceiverRoleError,
    WrongSenderRoleError,
)
from police_thief.protocol.messages import (
    Envelope,
    MessageType,
    new_envelope,
    new_message_id,
)
from police_thief.protocol.versions import (
    MANDATORY_CAPABILITIES,
    SOFTWARE_VERSION,
    SUPPORTED_CAPABILITIES,
)
from police_thief.strategy.heuristics import load_strategy
from police_thief.strategy.tracker import OpponentTracker
from police_thief.strategy.verbal import HintRequest, default_provider


@dataclass
class HandshakeState:
    """What the opponent has told us, and what we have told them.

    Note what is absent: anything about where the opponent *is*. The handshake
    establishes that both sides loaded the same physics; it conveys no game
    information at all.
    """

    opponent_name: str | None = None
    opponent_software_version: str | None = None
    opponent_capabilities: frozenset[str] = frozenset()
    opponent_config_sha256: str | None = None
    our_hello_acknowledged: bool = False
    our_config_accepted: bool = False
    opponent_ready: bool = False
    we_sent_ready: bool = False

    @property
    def complete(self) -> bool:
        return (
            self.our_hello_acknowledged
            and self.our_config_accepted
            and self.we_sent_ready
            and self.opponent_ready
        )


@dataclass
class PeerOrchestrator:
    """Owns one peer's lifecycle."""

    shared: SharedConfig
    private: PrivateConfig
    game_id: str
    client: PeerClient
    events: EventSink = field(default_factory=NullEventSink)
    clock: Clock = field(default_factory=SystemClock)
    id_factory: Callable[[], str] = new_message_id
    audit: AuditLog | None = None
    """The tamper-evident log. Optional so unit tests need no filesystem."""

    def __post_init__(self) -> None:
        self.role: Role = self.private.role
        self.opponent_role: Role = self.role.opponent
        self.machine = PeerStateMachine(now=self.clock.monotonic)
        self.handshake = HandshakeState()
        self.registry = MessageRegistry(
            capacity=self.shared.rate_limiter_gatekeeper.queue_depth
        )
        self.config_hash = config_sha256(self.shared.raw)
        # This peer's own truth. There is exactly one, for its own role.
        self.state: LocalState = LocalState.initial(self.role, self.shared)
        self.watchdog = Watchdog(
            timeout_sec=self.shared.network_and_league.watchdog_timeout_sec,
            on_stall=self._on_stall,
            clock=self.clock,
        )
        self.failure: str | None = None
        self.crypto = CommitRevealCoordinator(
            game_id=self.game_id, role=self.role
        )
        self.last_opponent_action: Action | None = None
        # Belief and scent about the opponent, plus the shipped default policy.
        # Both read only what this peer is legally entitled to know.
        self.tracker = OpponentTracker(
            role=self.role, config=self.shared, board=self.state.board
        )
        configured_class = (
            self.private.strategy.police_class
            if self.role is Role.POLICE
            else self.private.strategy.thief_class
        )
        self.strategy = load_strategy(self.role.value, configured_class)
        self.hints = default_provider()
        self.latest_opponent_hint: str = ""
        self.latest_opponent_intent: str = ""
        """The last hint the opponent revealed, and the intent it declared.

        Legal to display: the opponent chose to send it. The declared intent
        may be a lie -- that is the game, not a leak.
        """
        self.final_status: str | None = None
        self.opponent_audit_received = False
        """Set when we have verified the opponent's final reveal.

        The audit is *mutual* (E-36): neither peer may leave until both
        directions have completed, or the side that left first is unaudited.
        """
        self._sub_game_opened = False
        # Holds a message that arrived one turn early. See peer/pending.py.
        self.pending = PendingTurnBuffer(
            capacity=self.shared.rate_limiter_gatekeeper.queue_depth
        )

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def build_gatekeeper(
        shared: SharedConfig, clock: Clock | None = None
    ) -> Gatekeeper:
        return Gatekeeper(GatekeeperLimits.from_config(shared), clock)

    @staticmethod
    def build_retry_policy(shared: SharedConfig) -> RetryPolicy:
        return RetryPolicy.from_config(shared)

    # ------------------------------------------------------------------
    # Inbound: the server's single callback
    # ------------------------------------------------------------------

    async def handle_message(self, envelope: Envelope) -> Mapping[str, Any]:
        """Handle one validated inbound message.

        Identity is checked before anything else, then duplicates, then state
        legality. Only after all three does the message get acted on.
        """
        self._check_identity(envelope)
        self.watchdog.heartbeat()

        hit = self.registry.lookup(envelope.message_id, envelope.payload)
        if hit is not None:
            self.events.emit(
                "duplicate_suppressed",
                message_id=envelope.message_id,
                message_type=envelope.message_type.value,
            )
            return hit.response

        response = await self._act_on(envelope)
        self.registry.record(envelope.message_id, envelope.payload, response)
        return response

    def _check_identity(self, envelope: Envelope) -> None:
        if envelope.game_id != self.game_id:
            raise WrongGameIdError(
                f"message belongs to game {envelope.game_id!r}, "
                f"this peer is playing {self.game_id!r}"
            )
        if envelope.sender_role is not self.opponent_role:
            raise WrongSenderRoleError(
                f"sender claims role {envelope.sender_role.value!r}; this "
                f"peer's opponent is {self.opponent_role.value!r}"
            )
        if envelope.receiver_role is not self.role:
            raise WrongReceiverRoleError(
                f"message is addressed to {envelope.receiver_role.value!r}, "
                f"this peer is {self.role.value!r}"
            )

    async def _act_on(self, envelope: Envelope) -> Mapping[str, Any]:
        kind = envelope.message_type

        if kind is MessageType.HEALTH_CHECK:
            return _ok(envelope, MessageType.ACK, acknowledged_message_id=envelope.message_id)

        if kind is MessageType.HELLO:
            return self._on_hello(envelope)

        if kind is MessageType.CONFIG_HASH:
            return self._on_config_hash(envelope)

        if kind is MessageType.READY:
            return self._on_ready(envelope)

        if kind in (MessageType.COMMIT, MessageType.REVEAL):
            early = self._buffer_if_early(envelope)
            if early is not None:
                return early

        if kind is MessageType.COMMIT:
            return self._on_commit(envelope)

        if kind is MessageType.REVEAL:
            return self._on_reveal(envelope)

        if kind is MessageType.FINAL_REVEAL:
            return self._on_final_reveal(envelope)

        if kind is MessageType.TURN_ABORT:
            self.crypto.abandon_turn("opponent aborted")
            self.events.emit(
                "turn_aborted",
                reason=str(envelope.payload.get("reason", ""))[:200],
            )
            return _ok(
                envelope,
                MessageType.ACK,
                acknowledged_message_id=envelope.message_id,
            )

        if kind in (MessageType.GAME_FINISHED, MessageType.SHUTDOWN):
            self.events.emit(
                "peer_finished",
                message_type=kind.value,
                reason=str(envelope.payload.get("reason", ""))[:200],
            )
            return _ok(
                envelope,
                MessageType.ACK,
                acknowledged_message_id=envelope.message_id,
            )

        if kind is MessageType.ERROR:
            self.events.emit(
                "peer_error",
                code=str(envelope.payload.get("code", ""))[:100],
                detail=str(envelope.payload.get("detail", ""))[:200],
            )
            return _ok(
                envelope,
                MessageType.ACK,
                acknowledged_message_id=envelope.message_id,
            )

        raise InvalidPeerStateError(
            f"message type {kind.value!r} is not accepted in phase 2"
        )

    def _on_hello(self, envelope: Envelope) -> Mapping[str, Any]:
        capabilities = frozenset(envelope.payload["capabilities"])
        missing = MANDATORY_CAPABILITIES - capabilities
        if missing:
            raise MissingCapabilityError(
                f"opponent does not support required capabilities: "
                f"{sorted(missing)}"
            )
        self.handshake.opponent_name = envelope.payload["peer_name"]
        self.handshake.opponent_software_version = envelope.payload[
            "software_version"
        ]
        self.handshake.opponent_capabilities = capabilities
        self.events.emit(
            "hello_received",
            peer_name=self.handshake.opponent_name,
            opponent_software_version=self.handshake.opponent_software_version,
        )
        return _ok(
            envelope,
            MessageType.HELLO,
            peer_name=self.private.game.group_name,
            software_version=SOFTWARE_VERSION,
            capabilities=sorted(SUPPORTED_CAPABILITIES),
        )

    def _on_config_hash(self, envelope: Envelope) -> Mapping[str, Any]:
        theirs = envelope.payload["config_sha256"]
        self.handshake.opponent_config_sha256 = theirs

        if theirs != self.config_hash:
            self.events.emit(
                "config_rejected",
                our_config_sha256=self.config_hash,
                their_config_sha256=theirs,
            )
            return _ok(
                envelope,
                MessageType.CONFIG_REJECTED,
                reason=(
                    "configuration hashes differ; refusing to play because the "
                    "two peers do not share the same physics"
                ),
                our_config_sha256=self.config_hash,
                their_config_sha256=theirs,
            )

        self.events.emit("config_accepted", config_sha256=self.config_hash)
        return _ok(
            envelope, MessageType.CONFIG_ACCEPTED, config_sha256=self.config_hash
        )

    def _on_ready(self, envelope: Envelope) -> Mapping[str, Any]:
        self.handshake.opponent_ready = True
        self.events.emit("peer_ready_received")
        self._maybe_become_ready()
        return _ok(
            envelope,
            MessageType.ACK,
            acknowledged_message_id=envelope.message_id,
        )

    # ------------------------------------------------------------------
    # Inbound: the cryptographic turn
    # ------------------------------------------------------------------

    def _expected_turn(self) -> int:
        """The turn we are on, or the one we are about to start.

        Between turns ``crypto.current`` is ``None`` -- the previous turn has
        finished and the next has not begun -- which is exactly the window the
        race falls into. Treating the next turn as expected during that gap is
        most of the fix.
        """
        if self.crypto.current is not None:
            return self.crypto.current.turn
        if self.crypto.completed_turns:
            return max(self.crypto.completed_turns) + 1
        return 1

    def _buffer_if_early(self, envelope: Envelope) -> Mapping[str, Any] | None:
        """Hold a message for the next turn, or let it through.

        Returns an acknowledgement when the message is buffered, ``None`` when
        it should be processed now. Anything stale or more than one turn ahead
        raises, exactly as before.
        """
        turn = envelope.turn_number
        if turn is None:
            return None

        expected = self._expected_turn()
        if turn <= expected:
            return None  # current or stale -- the normal path decides which

        if turn > expected + MAX_TURNS_AHEAD:
            self.events.emit(
                "future_message_rejected",
                turn=turn,
                expected=expected,
                message_type=envelope.message_type.value,
            )
            raise FutureTurnMessageError(
                f"turn {turn} is more than {MAX_TURNS_AHEAD} turn ahead of "
                f"turn {expected}; a peer that far ahead is playing a "
                f"different game"
            )

        try:
            held = self.pending.lookup(envelope.message_id, envelope.payload)
        except ConflictingDuplicateError:
            self.events.emit(
                "buffer_conflict",
                turn=turn,
                message_id=envelope.message_id,
            )
            raise
        if held is not None:
            return held.response  # exact retry: same acknowledgement

        response = _ok(
            envelope,
            MessageType.COMMIT_ACK
            if envelope.message_type is MessageType.COMMIT
            else MessageType.REVEAL_ACK,
            **(
                {
                    "commitment": envelope.payload.get("commitment", ""),
                    "locked": True,
                }
                if envelope.message_type is MessageType.COMMIT
                else {"accepted": True}
            ),
        )
        try:
            self.pending.add(envelope, response)
        except BufferOverflowError as exc:
            self.events.emit("future_message_rejected", turn=turn, reason="overflow")
            raise InvalidPeerStateError(str(exc)) from exc

        self.events.emit(
            "future_message_buffered",
            turn=turn,
            expected=expected,
            message_type=envelope.message_type.value,
            held=len(self.pending),
        )
        return response

    async def _drain_pending(self, turn: int) -> None:
        """Process anything buffered for ``turn``, in a deterministic order.

        Called once the local turn has advanced, so each message now runs
        through the ordinary handler with its turn genuinely current -- the
        ordering guarantees are the same ones that applied to a message which
        arrived on time.
        """
        for message in self.pending.take_for_turn(turn):
            self.events.emit(
                "buffered_message_processed",
                turn=turn,
                message_type=message.envelope.message_type.value,
            )
            if message.envelope.message_type is MessageType.COMMIT:
                self._on_commit(message.envelope)
            else:
                self._on_reveal(message.envelope)

    def _on_commit(self, envelope: Envelope) -> Mapping[str, Any]:
        """Record the opponent's commitment.

        Only the digest arrives. Nothing here learns anything about the move --
        which is the point of the phase.
        """
        turn = envelope.turn_number
        commitment = envelope.payload["commitment"]
        self.crypto.begin_turn(turn)
        is_new = self.crypto.record_opponent_commit(turn, commitment)

        if self.audit is not None:
            self.audit.append(
                AuditEventType.OPPONENT_COMMIT,
                {"commitment": commitment, "message_id": envelope.message_id},
                turn_number=turn,
            )
        self.events.emit(
            "opponent_commit",
            turn=turn,
            commitment=commitment[:16],
            first_time=is_new,
        )
        return _ok(
            envelope, MessageType.COMMIT_ACK, commitment=commitment, locked=True
        )

    def _on_reveal(self, envelope: Envelope) -> Mapping[str, Any]:
        """Accept the opponent's revealed action.

        Binding is checked, not the hash: without the nonce there is nothing to
        recompute yet (E-18). The commitment is verified at the final audit.
        """
        turn = envelope.turn_number
        sealed = envelope.payload["sealed"]
        action = self.crypto.accept_opponent_reveal(turn, sealed)

        if self.audit is not None:
            self.audit.append(
                AuditEventType.OPPONENT_REVEAL,
                {"sealed": dict(sealed), "message_id": envelope.message_id},
                turn_number=turn,
            )
        self.events.emit("opponent_reveal", turn=turn, action=str(action))
        self.last_opponent_action = action
        return _ok(envelope, MessageType.REVEAL_ACK, accepted=True)

    def _on_final_reveal(self, envelope: Envelope) -> Mapping[str, Any]:
        """Verify every opponent commitment now that the nonces are disclosed.

        This is where tampering is caught (Ch. 5, PDF p. 55; E-19).
        """
        records = envelope.payload["records"]
        verified = self.crypto.verify_final_reveal(records)

        if self.audit is not None:
            self.audit.append(
                AuditEventType.AUDIT_RESULT,
                {"result": "verified", "turns": len(verified)},
            )
        self.opponent_audit_received = True
        self.events.emit("audit_passed", turns=len(verified))
        return _ok(
            envelope,
            MessageType.FINAL_REVEAL_ACK,
            audit="OK",
            verified_turns=len(verified),
        )

    # ------------------------------------------------------------------
    # Outbound: the cryptographic turn
    # ------------------------------------------------------------------

    def choose_action(self) -> Action:
        """Ask the strategy for this turn's action.

        Called before sealing. The strategy sees a :class:`LocalView` built from
        this peer's own state plus its belief and the opponent's scent -- there
        is no path from here to the opponent's true position.
        """
        self.tracker.note_own_position(self.state.position)
        return self.strategy.choose(self.tracker.view(self.state))

    async def play_turn(
        self,
        turn: int,
        action: Action | None = None,
        *,
        hint: str = "",
        intent: str = "truth",
    ) -> Action:
        """Run one full commit-reveal turn. Returns the opponent's action.

        The ordering below is the protocol's safety property. Each step is a
        state transition, and the transition table makes the unsafe orderings
        unreachable rather than merely unwise.
        """
        self.open_sub_game()
        self.machine.transition(PeerState.SELECTING_ACTION, f"turn {turn}")
        if action is None:
            action = self.choose_action()

        if not hint:
            # The verbal layer runs *after* the move is decided and cannot
            # change it. It only describes -- truthfully or not.
            composed = self.hints.compose(
                HintRequest(
                    game_id=self.game_id,
                    role=self.role.value,
                    turn=turn,
                    actual_direction=getattr(action, "direction", None),
                    map_area=self.shared.world.map_area,
                    max_words=self.shared.world.hint_max_words,
                )
            )
            hint, intent = composed.text, composed.intent

        # Anything the opponent sent early for this turn is now due. Drained
        # before we commit, so a buffered commit is already recorded by the
        # time we start waiting for it.
        await self._drain_pending(turn)

        # 1. Seal privately. The nonce is created here and never leaves.
        state_hash = local_state_hash(self.state.to_public_dict())
        commitment = self.crypto.seal(
            turn=turn,
            action=action,
            hint=hint,
            intent=intent,
            state_hash=state_hash,
        )
        self.machine.transition(PeerState.LOCAL_ACTION_SEALED, "sealed")
        if self.audit is not None:
            # The commitment only. Logging the action here would defeat it.
            self.audit.append(
                AuditEventType.LOCAL_COMMIT,
                {"commitment": commitment},
                turn_number=turn,
            )

        # 2/3. Send the digest **while** waiting for theirs.
        #
        # These must overlap. Both peers act at once, so if each blocked on its
        # own send before starting to wait, each would be holding its event loop
        # inside a request whose answer depends on the other making progress --
        # a deadlock that only shows up between two real processes.
        self.machine.transition(
            PeerState.WAITING_FOR_OPPONENT_COMMIT, "commit sent"
        )
        sending = asyncio.create_task(
            self.client.send(
                self._envelope(
                    MessageType.COMMIT,
                    turn_number=turn,
                    **self.crypto.commit_payload(turn),
                )
            )
        )
        arrived = await self._await_condition(
            lambda: self.crypto.reveal_allowed(turn)
        )
        reply = await self._settle(sending)

        if reply is not None and not reply.ok:
            return self._fail_turn(turn, f"commit rejected: {reply.error}")
        if not arrived and not self.crypto.reveal_allowed(turn):
            return self._fail_turn(turn, "opponent commitment never arrived")
        self.machine.transition(PeerState.BOTH_COMMITS_RECEIVED, "both committed")
        self.machine.transition(PeerState.REVEAL_ALLOWED, "reveal permitted")

        # 4. Reveal the action -- still without the nonce.
        payload = self.crypto.reveal_payload(turn)
        self.machine.transition(PeerState.LOCAL_REVEAL_SENT, "reveal sent")
        if self.audit is not None:
            self.audit.append(
                AuditEventType.LOCAL_REVEAL,
                {"sealed": payload["sealed"]},
                turn_number=turn,
            )
        sending = asyncio.create_task(
            self.client.send(
                self._envelope(MessageType.REVEAL, turn_number=turn, **payload)
            )
        )

        # 5. Again overlapping: wait for theirs while ours is in flight.
        self.machine.transition(
            PeerState.WAITING_FOR_OPPONENT_REVEAL, "awaiting reveal"
        )
        arrived = await self._await_condition(
            lambda: self.crypto.current is not None
            and self.crypto.current.opponent_reveal is not None
        )
        reply = await self._settle(sending)

        if reply is not None and not reply.ok:
            return self._fail_turn(turn, f"reveal rejected: {reply.error}")
        if not arrived:
            return self._fail_turn(turn, "opponent reveal never arrived")

        self.machine.transition(PeerState.VERIFYING_REVEAL, "verifying")
        crypto_turn = self.crypto.current
        if crypto_turn is None or crypto_turn.opponent_reveal is None:
            return self._fail_turn(turn, "opponent reveal never arrived")

        opponent_action = decode_action(crypto_turn.opponent_reveal["action"])
        # The hint the opponent chose to send us, and the intent it
        # declared. Legal to display; the intent may well be a lie.
        self.latest_opponent_hint = str(
            crypto_turn.opponent_reveal.get("hint", "")
        )
        self.latest_opponent_intent = str(
            crypto_turn.opponent_reveal.get("intent", "")
        )
        self.machine.transition(PeerState.BOTH_REVEALS_VERIFIED, "verified")

        # 6. Only now may anything be applied.
        self.machine.transition(PeerState.APPLYING_TURN, "applying")

        # Our own action moves our own state. The opponent's action updates our
        # belief and its reconstructed scent -- never a position field.
        try:
            self.state = apply_action(self.state, action, self.shared).state
        except DomainError as exc:
            return self._fail_turn(turn, f"our own action was illegal: {exc}")

        if isinstance(action, PlaceBarrier):
            self.tracker.observe_barrier(action.cell)
        self.tracker.observe_opponent_action(
            opponent_action, own_cell=self.state.position
        )
        # What they said, weighed against what the trail shows. Scent cannot be
        # forged, so a claim it contradicts costs the speaker trust instead of
        # moving our belief.
        self.tracker.note_hint(
            self.hints.interpret(self.latest_opponent_hint),
            own_cell=self.state.position,
        )
        if isinstance(opponent_action, PlaceBarrier):
            self.state = observe_barrier(self.state, opponent_action.cell)

        self.crypto.finish_turn(turn)
        self.machine.transition(PeerState.TURN_COMPLETE, "turn complete")

        if self.audit is not None:
            self.audit.append(
                AuditEventType.TURN_APPLIED,
                {"opponent_action": encode_action(opponent_action)},
                turn_number=turn,
            )
        self.events.emit("turn_complete", turn=turn)
        return opponent_action

    async def _settle(self, task: asyncio.Task[Any]) -> Any:
        """Collect an in-flight send without letting its failure mask progress.

        If our message reached the opponent but its acknowledgement did not come
        back, the turn has still progressed -- the opponent's own message proves
        it. Returning ``None`` lets the caller judge on what actually arrived
        rather than on a lost receipt.
        """
        try:
            return await task
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.events.emit("send_unacknowledged", error=type(exc).__name__)
            return None

    async def _await_condition(
        self, predicate: Callable[[], bool]
    ) -> bool:
        """Wait for an inbound fact, bounded.

        Bounded because an unbounded wait for the opponent is the deadlock
        Ch. 8 (PDF p. 79) exists to prevent: "the system does not get stuck
        waiting forever but moves in a controlled way". The per-attempt
        interval is derived from ``response_timeout_sec`` so the total wait
        respects the configured deadline rather than inventing one.
        """
        deadline = (
            self.clock.monotonic()
            + self.shared.network_and_league.response_timeout_sec
        )
        interval = 0.02
        while True:
            if predicate():
                return True
            if self.clock.monotonic() >= deadline:
                return predicate()
            await self.clock.sleep(interval)

    def _clear_pending(self, why: str) -> None:
        """Drop buffered messages whose turn will never run."""
        dropped = self.pending.clear()
        if dropped:
            self.events.emit("pending_buffer_cleared", dropped=dropped, reason=why)

    def _fail_turn(self, turn: int, detail: str) -> Any:
        """Enter the controlled failure path without leaking the nonce."""
        self.crypto.abandon_turn(detail)
        self._clear_pending("turn failed")
        self.failure = "turn_failed"
        self.events.emit("turn_failed", turn=turn, detail=detail[:200])
        if self.audit is not None:
            self.audit.append(
                AuditEventType.TURN_FAILED,
                {"detail": detail[:200]},
                turn_number=turn,
            )
        if not self.machine.is_terminal:
            try:
                self.machine.transition(PeerState.TURN_FAILED, detail[:60])
            except InvalidPeerStateError:
                self.machine.transition(PeerState.ERROR, detail[:60])
        raise CryptoTurnTimeoutError(f"turn {turn} failed: {detail}")

    async def send_final_reveal(self) -> int:
        """Disclose all our nonces and let the opponent audit us (E-18)."""
        payload = self.crypto.final_reveal_payload()
        if self.audit is not None:
            self.audit.append(
                AuditEventType.FINAL_REVEAL, payload  # the one nonce-bearing event
            )
        reply = await self.client.send(
            self._envelope(MessageType.FINAL_REVEAL, **payload)
        )
        if not reply.ok or reply.envelope is None:
            raise CommitmentMismatchError(
                f"the opponent rejected our final reveal: {reply.error}"
            )
        return int(reply.envelope.payload.get("verified_turns", 0))

    # ------------------------------------------------------------------
    # Outbound: the handshake we drive
    # ------------------------------------------------------------------

    def _envelope(
        self,
        message_type: MessageType,
        *,
        turn_number: int | None = None,
        **payload: Any,
    ) -> Envelope:
        return new_envelope(
            game_id=self.game_id,
            sender_role=self.role,
            receiver_role=self.opponent_role,
            message_type=message_type,
            payload=payload,
            turn_number=turn_number,
            message_id=self.id_factory(),
        )

    async def wait_for_peer(self, attempts: int = 30, interval: float = 1.0) -> bool:
        """Poll the opponent's liveness probe until it answers.

        The two processes start independently, so either may be first. Bounded
        by ``attempts`` -- a peer that waits forever for one that never arrives
        is the deadlock Ch. 8 warns about.
        """
        self.machine.transition(PeerState.CONNECTING, "waiting for opponent")
        for attempt in range(1, attempts + 1):
            if await self.client.health_check():
                self.events.emit("peer_reachable", attempts=attempt)
                return True
            await self.clock.sleep(interval)
        self.events.emit("peer_unreachable", attempts=attempts)
        self.machine.transition(PeerState.DISCONNECTED, "opponent never answered")
        self.failure = "peer_unavailable"
        return False

    async def perform_handshake(self) -> bool:
        """Hello, config hash, ready. Returns ``True`` on success."""
        self.machine.transition(PeerState.HELLO_EXCHANGE, "sending hello")
        hello = await self.client.send(
            self._envelope(
                MessageType.HELLO,
                peer_name=self.private.game.group_name,
                software_version=SOFTWARE_VERSION,
                capabilities=sorted(SUPPORTED_CAPABILITIES),
            )
        )
        if not hello.ok or hello.envelope is None:
            return self._fail("hello_rejected", hello.error or "no reply")

        payload = hello.envelope.payload
        capabilities = frozenset(payload.get("capabilities", []))
        missing = MANDATORY_CAPABILITIES - capabilities
        if missing:
            return self._fail(
                "missing_capability", f"opponent lacks {sorted(missing)}"
            )
        self.handshake.opponent_name = payload.get("peer_name")
        self.handshake.opponent_software_version = payload.get("software_version")
        self.handshake.opponent_capabilities = capabilities
        self.handshake.our_hello_acknowledged = True

        self.machine.transition(PeerState.CONFIG_EXCHANGE, "exchanging config hash")
        reply = await self.client.send(
            self._envelope(
                MessageType.CONFIG_HASH,
                config_sha256=self.config_hash,
                config_schema_version=self.shared.schema_version,
            )
        )
        if not reply.ok or reply.envelope is None:
            return self._fail("config_exchange_failed", reply.error or "no reply")

        if reply.envelope.message_type is MessageType.CONFIG_REJECTED:
            self.events.emit(
                "config_mismatch",
                our_config_sha256=self.config_hash,
                their_config_sha256=reply.envelope.payload.get(
                    "our_config_sha256", "?"
                ),
            )
            return self._fail(
                "config_mismatch",
                "the opponent rejected our configuration hash",
            )

        if reply.envelope.message_type is not MessageType.CONFIG_ACCEPTED:
            return self._fail(
                "unexpected_reply",
                f"expected config_accepted, got "
                f"{reply.envelope.message_type.value}",
            )

        theirs = reply.envelope.payload["config_sha256"]
        self.handshake.opponent_config_sha256 = theirs
        if theirs != self.config_hash:
            return self._fail(
                "config_mismatch",
                "the opponent's configuration hash differs from ours",
            )

        self.handshake.our_config_accepted = True
        self.machine.transition(PeerState.CONFIG_VERIFIED, "config hashes match")
        self.events.emit("handshake_ok", config_sha256=self.config_hash)

        self.machine.transition(PeerState.READY_WAIT, "announcing readiness")
        ready = await self.client.send(self._envelope(MessageType.READY))
        if not ready.ok:
            return self._fail("ready_rejected", ready.error or "no reply")
        self.handshake.we_sent_ready = True

        self._maybe_become_ready()
        return True

    async def await_ready(self, attempts: int = 60, interval: float = 0.5) -> bool:
        """Wait for the opponent's READY, which may arrive before or after ours."""
        for _ in range(attempts):
            if self.machine.state is PeerState.READY:
                return True
            if self.machine.is_terminal:
                return False
            await self.clock.sleep(interval)
        return self.machine.state is PeerState.READY

    def _maybe_become_ready(self) -> None:
        if self.handshake.complete and self.machine.state is PeerState.READY_WAIT:
            self.machine.transition(PeerState.READY, "both peers ready")
            self.events.emit("ready", config_sha256=self.config_hash)

    def _fail(self, code: str, detail: str) -> bool:
        self.failure = code
        self.events.emit("handshake_failed", code=code, detail=detail[:200])
        if not self.machine.is_terminal:
            self.machine.transition(PeerState.ERROR, code)
        return False

    def _on_stall(self, silence: float) -> None:
        """Watchdog callback: the peer has gone quiet (E-7).

        Records a structured operational failure and winds down. It does
        **not** decide a game result: the PDF defines a technical loss for a
        side that crashes or exceeds time (Ch. 3, PDF p. 38), but adjudicating
        that is league business, not something a peer declares about itself.
        """
        self.failure = "watchdog_stall"
        self.events.emit("watchdog_stall", silence_seconds=round(silence, 3))
        if not self.machine.is_terminal:
            self.machine.transition(PeerState.DISCONNECTED, "watchdog stall")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open_sub_game(self) -> None:
        """Record the preconditions a replay needs to check us against.

        Written once, before any turn. It pins what we claim to have been
        playing -- which config, which board, which resolution policies -- so an
        independent verifier can compare the two peers' claims rather than
        taking either on trust. Without this the logs cannot be told apart from
        two peers playing different games.
        """
        if self.audit is None or self._sub_game_opened:
            return
        self._sub_game_opened = True
        board = self.shared.board_and_agents
        self.audit.append(
            AuditEventType.SUB_GAME_START,
            {
                "config_sha256": self.config_hash,
                "grid_size": board.grid_size,
                "cop_start": list(board.cop_start),
                "thief_start": list(board.thief_start),
                "policy": {
                    "capture": DEFAULT_SIMULTANEITY_POLICY.name,
                    "blocked_move": BLOCKED_MOVE_BECOMES_STAY,
                },
            },
        )

    def close_sub_game(self, claimed: Mapping[str, Any] | None = None) -> None:
        """Record what we believe happened.

        A *claim*, not a finding: a live peer cannot compute the winner, having
        never seen its opponent's position. The replay recomputes the outcome
        from both logs and contradicts this if it disagrees.
        """
        if self.audit is None:
            return
        self.audit.append(
            AuditEventType.SUB_GAME_END,
            {
                "turns_played": len(self.crypto.completed_turns),
                "own_final_position": list(self.state.position.as_tuple()),
                "claimed": dict(claimed or {}),
            },
        )

    def mark_server_ready(self, url: str) -> None:
        self.machine.transition(PeerState.STARTING, "starting server")
        self.machine.transition(PeerState.SERVER_READY, "server listening")
        self.events.emit("server_ready", url=url)

    async def shutdown(self, reason: str = "normal") -> None:
        """Wind down cleanly from wherever we are."""
        await self.watchdog.stop()
        # Buffered messages belong to turns that will never run now.
        self._clear_pending("shutdown")
        if self.machine.is_terminal:
            self.events.emit("shutdown", reason=reason, state=self.machine.state.value)
            return
        try:
            self.machine.transition(PeerState.FINISHING, reason)
            self.machine.transition(PeerState.FINISHED, reason)
        except InvalidPeerStateError:
            # Already somewhere that cannot reach FINISHING; nothing to undo.
            pass
        self.events.emit("shutdown", reason=reason, state=self.machine.state.value)

    def status(self) -> dict[str, Any]:
        """A summary safe to show a user or a later GUI.

        Contains no opponent position, because there is none to contain.
        """
        return {
            "role": self.role.value,
            "game_id": self.game_id,
            "state": self.machine.state.value,
            "config_sha256": self.config_hash,
            "opponent_name": self.handshake.opponent_name,
            "opponent_ready": self.handshake.opponent_ready,
            "handshake_complete": self.handshake.complete,
            "failure": self.failure,
            "own_position": list(self.state.position.as_tuple()),
        }


def _ok(
    envelope: Envelope, message_type: MessageType, **payload: Any
) -> dict[str, Any]:
    return {
        "ok": True,
        "error": None,
        "envelope": envelope.reply(message_type, payload).to_wire(),
    }
