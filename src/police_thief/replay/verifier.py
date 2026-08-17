"""Two-log replay: reconstruct the sub-game and decide it independently.

The verification order matters, because each step presupposes the one before:

1. **Both hash chains** verify (a modified, deleted, reordered or duplicated
   record fails here, before anything is read as fact).
2. **Preconditions agree** -- same game, same sub-game, same config hash, same
   resolution policies. Different policies are *not* tampering; they are two
   honest peers computing different boards, so they get their own verdict.
3. **Commitments verify** against the final revealed nonces, in both
   directions: each peer's sealed record is re-hashed and compared both to its
   own `local_commit` and to what the other side recorded as `opponent_commit`.
4. **Each turn's reveal matches its final sealed record** -- the story told
   during play must match the story told at the audit.
5. **The game is replayed** through the agreed physics and simultaneity policy,
   which re-derives every position, barrier, capture and the terminal.
6. **The recomputed result is compared** to whatever the peers claimed.

Verdicts
--------
``VERIFIED_OK``      reconstruction succeeded and agrees with both logs
``TAMPERED``         a hash, a reveal or an action does not hold up
``INCOMPLETE``       the logs stop short -- missing final reveal, missing turns
``POLICY_MISMATCH``  the two peers were applying different resolution rules
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from police_thief.audit.verifier import load_records, verify_chain
from police_thief.config.models import SharedConfig
from police_thief.crypto.sealed import commitment_for_mapping
from police_thief.domain.actions import Move, PlaceBarrier
from police_thief.domain.capture import (
    evaluate_barrier_capture,
    evaluate_full_turn_capture,
)
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Direction, Role
from police_thief.domain.exceptions import BlockedCellError, DomainError
from police_thief.domain.scoring import ScoreResult, calculate_score
from police_thief.domain.simultaneity import (
    DEFAULT_SIMULTANEITY_POLICY,
    SimultaneityPolicy,
    TurnMovement,
)
from police_thief.domain.state import LocalState
from police_thief.domain.terminal import (
    TerminalResult,
    evaluate_move_ceiling,
    evaluate_survival,
)
from police_thief.domain.terminal import (
    capture as terminal_capture,
)
from police_thief.domain.transition import apply_action, observe_barrier
from police_thief.protocol.action_codec import decode_action


class Verdict(str, Enum):
    VERIFIED_OK = "VERIFIED OK"
    TAMPERED = "TAMPERED"
    INCOMPLETE = "INCOMPLETE"
    POLICY_MISMATCH = "POLICY MISMATCH"


@dataclass(frozen=True, slots=True)
class TurnFrame:
    """One reconstructed turn, for the viewer."""

    turn: int
    cop_position: Coordinate
    thief_position: Coordinate
    barriers: tuple[Coordinate, ...]
    cop_action: str
    thief_action: str
    cop_hint: str
    thief_hint: str
    cop_intent: str
    thief_intent: str
    note: str = ""


@dataclass
class ReplayVerdict:
    """The outcome of an independent reconstruction."""

    verdict: Verdict
    reason: str = ""
    turns_verified: int = 0
    terminal: TerminalResult | None = None
    score: ScoreResult | None = None
    frames: list[TurnFrame] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    disagreements: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.VERIFIED_OK

    def __bool__(self) -> bool:
        return self.ok

    def describe(self) -> str:
        head = self.verdict.value
        if self.terminal is not None and self.score is not None:
            winner = (
                self.terminal.winner.value if self.terminal.winner else "nobody"
            )
            detail = (
                f" ({self.terminal.capture_reason.value})"
                if self.terminal.capture_reason
                else ""
            )
            head += (
                f" — {self.terminal.reason.value}{detail} on turn "
                f"{self.terminal.turn}; winner {winner}; "
                f"cop {self.score.cop}, thief {self.score.thief}"
            )
        if self.reason:
            head += f" — {self.reason}"
        return head


# ----------------------------------------------------------------------
# Log indexing
# ----------------------------------------------------------------------


def _events(records: Sequence[Mapping[str, Any]], kind: str):
    return [r for r in records if r["event_type"] == kind]


def _one(records, kind: str) -> Mapping[str, Any] | None:
    found = _events(records, kind)
    return found[0] if found else None


def _sealed_by_turn(records) -> dict[int, dict[str, Any]]:
    """Each peer's own final-reveal records, keyed by turn, nonce included."""
    final = _one(records, "final_reveal")
    if final is None:
        return {}
    return {r["turn"]: dict(r) for r in final["payload"]["records"]}


def _commitments(records, kind: str) -> dict[int, str]:
    return {
        r["turn_number"]: r["payload"]["commitment"]
        for r in _events(records, kind)
        if r["turn_number"] is not None
    }


def _reveals(records, kind: str) -> dict[int, dict[str, Any]]:
    return {
        r["turn_number"]: dict(r["payload"]["sealed"])
        for r in _events(records, kind)
        if r["turn_number"] is not None
    }


# ----------------------------------------------------------------------
# Verification
# ----------------------------------------------------------------------


def replay_logs(
    cop_records: Sequence[Mapping[str, Any]],
    thief_records: Sequence[Mapping[str, Any]],
    config: SharedConfig,
    *,
    policy: SimultaneityPolicy | None = None,
) -> ReplayVerdict:
    """Reconstruct and decide a sub-game from both peers' logs."""

    # --- 1. hash chains ------------------------------------------------
    for label, records in (("cop", cop_records), ("thief", thief_records)):
        chain = verify_chain(list(records))
        if not chain:
            return ReplayVerdict(
                Verdict.TAMPERED,
                f"{label} log: {chain.describe()}",
            )

    # --- 2. preconditions ----------------------------------------------
    starts = {
        "cop": _one(cop_records, "sub_game_start"),
        "thief": _one(thief_records, "sub_game_start"),
    }
    if starts["cop"] is None or starts["thief"] is None:
        return ReplayVerdict(
            Verdict.INCOMPLETE,
            "one or both logs lack a sub_game_start record, so there is "
            "nothing to check the game's preconditions against",
        )

    cop_start, thief_start = starts["cop"], starts["thief"]

    if cop_start["game_id"] != thief_start["game_id"]:
        return ReplayVerdict(
            Verdict.TAMPERED,
            f"the two logs describe different games: "
            f"{cop_start['game_id']!r} and {thief_start['game_id']!r}",
        )
    if cop_start["sub_game"] != thief_start["sub_game"]:
        return ReplayVerdict(
            Verdict.TAMPERED,
            f"sub-game mismatch: {cop_start['sub_game']} and "
            f"{thief_start['sub_game']}",
        )

    # Policy disagreement is checked before config, because two peers running
    # different rules is a different kind of failure from a forged log: nobody
    # necessarily cheated, they simply were not playing the same game.
    cop_policy = cop_start["payload"].get("policy", {})
    thief_policy = thief_start["payload"].get("policy", {})
    if cop_policy != thief_policy:
        return ReplayVerdict(
            Verdict.POLICY_MISMATCH,
            f"the peers applied different resolution policies: "
            f"cop {cop_policy} versus thief {thief_policy}",
        )

    if cop_start["payload"]["config_sha256"] != thief_start["payload"][
        "config_sha256"
    ]:
        return ReplayVerdict(
            Verdict.TAMPERED,
            "the peers logged different configuration hashes, so they were "
            "not enforcing the same physics",
        )

    if policy is None:
        policy = DEFAULT_SIMULTANEITY_POLICY
    if cop_policy.get("capture") not in (None, policy.name):
        return ReplayVerdict(
            Verdict.POLICY_MISMATCH,
            f"the logs were produced under capture policy "
            f"{cop_policy.get('capture')!r} but this replay is applying "
            f"{policy.name!r}; the verifier will not silently substitute one",
        )

    # --- 3. commitments against the revealed nonces --------------------
    sealed = {
        Role.POLICE: _sealed_by_turn(cop_records),
        Role.THIEF: _sealed_by_turn(thief_records),
    }
    if not sealed[Role.POLICE] or not sealed[Role.THIEF]:
        return ReplayVerdict(
            Verdict.INCOMPLETE,
            "a final reveal is missing, so the commitments cannot be checked; "
            "an unaudited log proves nothing",
        )

    own_commit = {
        Role.POLICE: _commitments(cop_records, "local_commit"),
        Role.THIEF: _commitments(thief_records, "local_commit"),
    }
    seen_commit = {
        Role.POLICE: _commitments(thief_records, "opponent_commit"),
        Role.THIEF: _commitments(cop_records, "opponent_commit"),
    }
    own_reveal = {
        Role.POLICE: _reveals(cop_records, "local_reveal"),
        Role.THIEF: _reveals(thief_records, "local_reveal"),
    }

    turns = sorted(set(sealed[Role.POLICE]) & set(sealed[Role.THIEF]))
    if not turns:
        return ReplayVerdict(Verdict.INCOMPLETE, "no turns are covered by both logs")

    for role in (Role.POLICE, Role.THIEF):
        for turn in turns:
            record = sealed[role].get(turn)
            if record is None:
                return ReplayVerdict(
                    Verdict.INCOMPLETE,
                    f"{role.value} did not reveal turn {turn}",
                )
            try:
                recomputed = commitment_for_mapping(record)
            except Exception as exc:
                return ReplayVerdict(
                    Verdict.TAMPERED,
                    f"{role.value} turn {turn}: sealed record is invalid: {exc}",
                )

            declared = own_commit[role].get(turn)
            if declared is None:
                return ReplayVerdict(
                    Verdict.INCOMPLETE,
                    f"{role.value} never logged a commitment for turn {turn}",
                )
            if recomputed != declared:
                return ReplayVerdict(
                    Verdict.TAMPERED,
                    f"{role.value} turn {turn}: the revealed record hashes to "
                    f"{recomputed[:12]}… but {role.value} committed "
                    f"{declared[:12]}…",
                )

            # The opponent's independent record of the same commitment. This is
            # what makes a one-sided forgery pointless: both logs would have to
            # agree on the lie.
            witnessed = seen_commit[role].get(turn)
            if witnessed is not None and witnessed != declared:
                return ReplayVerdict(
                    Verdict.TAMPERED,
                    f"{role.value} turn {turn}: the two logs disagree about "
                    f"what was committed",
                )

            # --- 4. the turn reveal must match the final sealed record ---
            during = own_reveal[role].get(turn)
            if during is not None:
                without_nonce = {
                    k: v for k, v in record.items() if k != "nonce"
                }
                if during != without_nonce:
                    return ReplayVerdict(
                        Verdict.TAMPERED,
                        f"{role.value} turn {turn}: the final reveal "
                        f"contradicts what was revealed during the turn",
                    )

    # --- 5. replay the physics -----------------------------------------
    return _reconstruct(
        turns, sealed, config, policy, cop_records, thief_records
    )


def _reconstruct(
    turns, sealed, config, policy, cop_records, thief_records
) -> ReplayVerdict:
    """Re-derive every position, barrier, capture and the terminal."""
    cop = LocalState.initial(Role.POLICE, config)
    thief = LocalState.initial(Role.THIEF, config)
    frames: list[TurnFrame] = []
    terminal: TerminalResult | None = None

    for turn in turns:
        cop_record = sealed[Role.POLICE][turn]
        thief_record = sealed[Role.THIEF][turn]

        if cop_record["role"] != Role.POLICE.value:
            return ReplayVerdict(
                Verdict.TAMPERED, f"turn {turn}: cop record claims another role"
            )
        if thief_record["role"] != Role.THIEF.value:
            return ReplayVerdict(
                Verdict.TAMPERED,
                f"turn {turn}: thief record claims another role",
            )

        try:
            cop_action = decode_action(cop_record["action"])
            thief_action = decode_action(thief_record["action"])
        except Exception as exc:
            return ReplayVerdict(
                Verdict.TAMPERED, f"turn {turn}: undecodable action: {exc}"
            )

        cop_before, thief_before = cop.position, thief.position
        note = ""

        # Cop acts. An illegal action is proof the peer did not enforce the
        # physics it agreed to -- the opponent should have rejected it.
        try:
            result = apply_action(cop, cop_action, config)
        except DomainError as exc:
            return ReplayVerdict(
                Verdict.TAMPERED,
                f"turn {turn}: the cop's action was illegal: {exc}",
            )
        cop = result.state

        if result.barrier_cell is not None:
            thief = observe_barrier(thief, result.barrier_cell)
            verdict = evaluate_barrier_capture(result.barrier_cell, thief.position)
            if verdict:
                terminal = terminal_capture(turn, verdict.reason)

        if terminal is None:
            try:
                thief_result = apply_action(thief, thief_action, config)
            except BlockedCellError:
                # Q-18: the barrier landed on the cell the thief had chosen.
                # Resolved by the agreed policy, not by this verifier.
                note = "blocked_move_becomes_stay"
                thief_result = apply_action(thief, Move(Direction.STAY), config)
            except DomainError as exc:
                return ReplayVerdict(
                    Verdict.TAMPERED,
                    f"turn {turn}: the thief's action was illegal: {exc}",
                )
            thief = thief_result.state
            if isinstance(thief_action, PlaceBarrier):
                return ReplayVerdict(
                    Verdict.TAMPERED,
                    f"turn {turn}: the thief placed a barrier, which only the "
                    f"cop may do",
                )

            cop = cop.advanced()
            thief = thief.advanced()

            movement = TurnMovement(
                cop_before=cop_before,
                cop_after=cop.position,
                thief_before=thief_before,
                thief_after=thief.position,
            )
            verdict = evaluate_full_turn_capture(movement, thief, config, policy)
            if verdict:
                terminal = terminal_capture(turn, verdict.reason)
            else:
                terminal = evaluate_survival(turn, config) or evaluate_move_ceiling(
                    turn, config
                )

        frames.append(
            TurnFrame(
                turn=turn,
                cop_position=cop.position,
                thief_position=thief.position,
                barriers=tuple(sorted(cop.board.barriers)),
                cop_action=str(cop_action),
                thief_action=str(thief_action),
                cop_hint=cop_record.get("hint", ""),
                thief_hint=thief_record.get("hint", ""),
                cop_intent=cop_record.get("intent", ""),
                thief_intent=thief_record.get("intent", ""),
                note=note,
            )
        )

        if terminal is not None:
            break

    if terminal is None:
        return ReplayVerdict(
            Verdict.INCOMPLETE,
            f"the logs cover {len(turns)} turn(s) but the sub-game never "
            f"reached a terminal state",
            turns_verified=len(turns),
            frames=frames,
        )

    score = calculate_score(terminal, config)

    # --- 6. compare with whatever the peers claimed --------------------
    disagreements: list[str] = []
    claims: dict[str, Any] = {}
    for label, records in (("cop", cop_records), ("thief", thief_records)):
        end = _one(records, "sub_game_end")
        if end is None:
            continue
        claimed = end["payload"].get("claimed") or {}
        claims[label] = claimed
        for key, recomputed in (
            ("cop_score", score.cop),
            ("thief_score", score.thief),
            ("winner", terminal.winner.value if terminal.winner else None),
            ("reason", terminal.reason.value),
        ):
            if key in claimed and claimed[key] != recomputed:
                disagreements.append(
                    f"{label} claimed {key}={claimed[key]!r}, "
                    f"reconstruction gives {recomputed!r}"
                )

    if disagreements:
        return ReplayVerdict(
            Verdict.TAMPERED,
            "a peer's claimed result contradicts the reconstruction: "
            + "; ".join(disagreements),
            turns_verified=len(frames),
            terminal=terminal,
            score=score,
            frames=frames,
            claims=claims,
            disagreements=disagreements,
        )

    return ReplayVerdict(
        Verdict.VERIFIED_OK,
        turns_verified=len(frames),
        terminal=terminal,
        score=score,
        frames=frames,
        claims=claims,
    )


def replay_files(
    cop_log: str | Path,
    thief_log: str | Path,
    config: SharedConfig,
    *,
    policy: SimultaneityPolicy | None = None,
) -> ReplayVerdict:
    """Replay from two JSONL files on disk."""
    for path in (cop_log, thief_log):
        if not Path(path).exists():
            return ReplayVerdict(Verdict.INCOMPLETE, f"no log at {path}")
    try:
        cop_records = load_records(cop_log)
        thief_records = load_records(thief_log)
    except json.JSONDecodeError as exc:
        return ReplayVerdict(Verdict.TAMPERED, f"malformed log line: {exc}")
    return replay_logs(cop_records, thief_records, config, policy=policy)
