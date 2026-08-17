"""The commit-reveal coordinator: ordering, duplicates, replay, verification."""

from __future__ import annotations

import pytest

from police_thief.crypto.coordinator import CommitRevealCoordinator
from police_thief.crypto.exceptions import (
    CommitAlreadyExistsError,
    CommitmentMismatchError,
    ConflictingCommitError,
    ConflictingRevealError,
    FutureTurnMessageError,
    InvalidRevealError,
    MissingCommitError,
    RevealNotAllowedError,
    StaleTurnMessageError,
)
from police_thief.domain.actions import Move
from police_thief.domain.enums import Direction, Role

STATE_HASH = "a" * 64
OPP_COMMIT = "f" * 64


def cop() -> CommitRevealCoordinator:
    return CommitRevealCoordinator(game_id="g1", role=Role.POLICE)


def thief() -> CommitRevealCoordinator:
    return CommitRevealCoordinator(game_id="g1", role=Role.THIEF)


def seal(coord: CommitRevealCoordinator, turn: int = 1, **overrides) -> str:
    base = {
        "turn": turn,
        "action": Move(Direction.N),
        "hint": "a hint",
        "intent": "truth",
        "state_hash": STATE_HASH,
    }
    base.update(overrides)
    return coord.seal(**base)


def full_turn(a: CommitRevealCoordinator, b: CommitRevealCoordinator, turn: int = 1):
    """Drive one complete turn between two coordinators."""
    ca = seal(a, turn, action=Move(Direction.N))
    cb = seal(b, turn, action=Move(Direction.S))
    a.record_opponent_commit(turn, cb)
    b.record_opponent_commit(turn, ca)
    ra = a.reveal_payload(turn)
    rb = b.reveal_payload(turn)
    b.accept_opponent_reveal(turn, ra["sealed"])
    a.accept_opponent_reveal(turn, rb["sealed"])
    a.finish_turn(turn)
    b.finish_turn(turn)
    return ra, rb


# ----------------------------------------------------------------------
# Ordering -- the safety property
# ----------------------------------------------------------------------


def test_commit_payload_contains_only_the_digest():
    """Anything narrowing the move space would defeat the commitment."""
    coord = cop()
    seal(coord)
    payload = coord.commit_payload(1)

    assert set(payload) == {"commitment", "commitment_schema"}
    body = str(payload)
    for leak in ("N", "move", "nonce", "hint", "truth", "action"):
        assert leak not in body.replace("commitment_schema", "")


def test_reveal_is_forbidden_before_the_opponent_commits():
    coord = cop()
    seal(coord)
    assert not coord.reveal_allowed(1)
    with pytest.raises(RevealNotAllowedError, match="before both commitments"):
        coord.reveal_payload(1)


def test_reveal_is_allowed_once_both_commitments_exist():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    assert coord.reveal_allowed(1)
    assert "sealed" in coord.reveal_payload(1)


def test_reveal_payload_never_contains_the_nonce():
    """E-18: the nonce "remains hidden at this stage" (PDF p. 51)."""
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    payload = coord.reveal_payload(1)

    assert "nonce" not in payload["sealed"]
    assert "nonce" not in str(payload)


def test_local_nonce_never_leaves_the_coordinator_before_final_reveal():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    nonce = coord.current.local_record.nonce

    assert nonce not in str(coord.commit_payload(1))
    assert nonce not in str(coord.reveal_payload(1))
    # Only the final reveal discloses it.
    coord.accept_opponent_reveal(1, _opponent_sealed(1))
    coord.finish_turn(1)
    assert nonce in str(coord.final_reveal_payload())


def test_cannot_commit_twice_for_the_same_turn():
    coord = cop()
    seal(coord)
    with pytest.raises(CommitAlreadyExistsError, match="already committed"):
        seal(coord)


def test_reveal_without_a_prior_opponent_commit_is_rejected():
    coord = cop()
    seal(coord)
    with pytest.raises((MissingCommitError, RevealNotAllowedError)):
        coord.accept_opponent_reveal(1, _opponent_sealed(1))


# ----------------------------------------------------------------------
# Duplicates and conflicts
# ----------------------------------------------------------------------


def test_exact_duplicate_commit_is_idempotent():
    coord = cop()
    seal(coord)
    assert coord.record_opponent_commit(1, OPP_COMMIT) is True
    assert coord.record_opponent_commit(1, OPP_COMMIT) is False


def test_conflicting_commit_is_rejected():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    with pytest.raises(ConflictingCommitError, match="cannot be changed"):
        coord.record_opponent_commit(1, "e" * 64)


def test_malformed_commitment_is_rejected():
    coord = cop()
    seal(coord)
    with pytest.raises(InvalidRevealError, match="64 lowercase hex"):
        coord.record_opponent_commit(1, "not-a-digest")


def test_exact_duplicate_reveal_is_idempotent():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    sealed = _opponent_sealed(1)
    first = coord.accept_opponent_reveal(1, sealed)
    second = coord.accept_opponent_reveal(1, sealed)
    assert first == second


def test_conflicting_reveal_is_rejected():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    coord.accept_opponent_reveal(1, _opponent_sealed(1))
    with pytest.raises(ConflictingRevealError, match="cannot be retracted"):
        coord.accept_opponent_reveal(
            1, _opponent_sealed(1, action=Move(Direction.E))
        )


# ----------------------------------------------------------------------
# Replay and turn binding
# ----------------------------------------------------------------------


def test_reveal_for_a_stale_turn_is_rejected():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)
    seal(a, 2)
    with pytest.raises(StaleTurnMessageError, match="already complete"):
        a.begin_turn(1)


def test_reveal_for_a_future_turn_is_rejected():
    coord = cop()
    seal(coord, 1)
    with pytest.raises(FutureTurnMessageError):
        coord.record_opponent_commit(5, OPP_COMMIT)


def test_reveal_claiming_the_wrong_game_is_rejected():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    with pytest.raises(InvalidRevealError, match="claims game"):
        coord.accept_opponent_reveal(1, _opponent_sealed(1, game_id="other"))


def test_reveal_claiming_the_wrong_role_is_rejected():
    """A cop must not accept a reveal claiming to be from another cop."""
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    with pytest.raises(InvalidRevealError, match="claims role"):
        coord.accept_opponent_reveal(1, _opponent_sealed(1, role="police"))


def test_reveal_whose_body_disagrees_with_its_envelope_turn_is_rejected():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    with pytest.raises(InvalidRevealError, match="body claims turn"):
        coord.accept_opponent_reveal(1, _opponent_sealed(7))


def test_reveal_claiming_the_wrong_sub_game_is_rejected():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    with pytest.raises(InvalidRevealError, match="sub-game"):
        coord.accept_opponent_reveal(1, _opponent_sealed(1, sub_game=9))


# ----------------------------------------------------------------------
# Final reveal and audit -- where tampering is caught
# ----------------------------------------------------------------------


def test_a_clean_match_verifies():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)
    full_turn(a, b, turn=2)

    assert a.verify_final_reveal(b.final_reveal_payload()["records"]) == [
        "turn 1", "turn 2",
    ]
    assert b.verify_final_reveal(a.final_reveal_payload()["records"]) == [
        "turn 1", "turn 2",
    ]


def test_tampered_action_is_detected_at_audit():
    """Ch. 5, PDF p. 55: any mismatch proves tampering, not doubt."""
    a, b = cop(), thief()
    full_turn(a, b, turn=1)

    records = b.final_reveal_payload()["records"]
    records[0]["action"] = {"v": 1, "kind": "move", "direction": "W"}

    with pytest.raises(CommitmentMismatchError):
        a.verify_final_reveal(records)


def test_tampered_nonce_is_detected_at_audit():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)

    records = b.final_reveal_payload()["records"]
    records[0]["nonce"] = "c" * 32

    with pytest.raises(CommitmentMismatchError, match="does not match"):
        a.verify_final_reveal(records)


def test_tampered_hint_is_detected_at_audit():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)
    records = b.final_reveal_payload()["records"]
    records[0]["hint"] = "something else entirely"
    with pytest.raises(CommitmentMismatchError):
        a.verify_final_reveal(records)


def test_final_reveal_disagreeing_with_the_turn_reveal_is_detected():
    """Changing the story between the turn and the audit is caught."""
    a, b = cop(), thief()
    full_turn(a, b, turn=1)

    records = b.final_reveal_payload()["records"]
    records[0]["intent"] = "lie" if records[0]["intent"] == "truth" else "truth"

    with pytest.raises(CommitmentMismatchError):
        a.verify_final_reveal(records)


def test_final_reveal_for_an_uncommitted_turn_is_rejected():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)

    records = b.final_reveal_payload()["records"]
    records[0]["turn"] = 42

    with pytest.raises(MissingCommitError, match="no opponent commitment"):
        a.verify_final_reveal(records)


def test_final_reveal_with_a_malformed_record_is_rejected():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)
    records = b.final_reveal_payload()["records"]
    del records[0]["nonce"]
    with pytest.raises(CommitmentMismatchError, match="invalid sealed record"):
        a.verify_final_reveal(records)


# ----------------------------------------------------------------------
# Abandonment and cleanup
# ----------------------------------------------------------------------


def test_abandoning_a_turn_does_not_expose_the_nonce():
    coord = cop()
    seal(coord)
    nonce = coord.current.local_record.nonce

    assert coord.abandon_turn("timeout") == 1
    assert coord.current is None
    # The nonce is gone from the pending turn but remembered as unusable.
    assert coord.nonces.has_used(nonce)
    assert nonce not in str(coord.final_reveal_payload())


def test_abandoned_turn_cannot_resume_without_a_fresh_seal():
    coord = cop()
    seal(coord)
    coord.abandon_turn("timeout")
    with pytest.raises(MissingCommitError, match="no turn in progress"):
        coord.commit_payload(1)


def test_abandoning_when_no_turn_is_open_is_safe():
    assert cop().abandon_turn("nothing") is None


def test_finish_requires_a_complete_turn():
    coord = cop()
    seal(coord)
    coord.record_opponent_commit(1, OPP_COMMIT)
    with pytest.raises(RevealNotAllowedError, match="not complete"):
        coord.finish_turn(1)


def test_a_nonce_is_never_reused_across_turns():
    a, b = cop(), thief()
    full_turn(a, b, turn=1)
    full_turn(a, b, turn=2)
    nonces = [r.nonce for r in a.audit_trail]
    assert len(nonces) == len(set(nonces)) == 2


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------


def _opponent_sealed(turn: int, **overrides):
    from police_thief.crypto.sealed import SealedRecord

    base = {
        "game_id": "g1",
        "sub_game": 1,
        "turn": turn,
        "role": Role.THIEF,
        "state": "b" * 64,
        "action": Move(Direction.S),
        "hint": "their hint",
        "intent": "lie",
        "nonce": "9" * 32,
    }
    plain = {k: v for k, v in overrides.items() if k in ("game_id", "sub_game")}
    base.update({k: v for k, v in overrides.items() if k not in plain})
    if "role" in overrides and isinstance(overrides["role"], str):
        base["role"] = Role(overrides["role"])
    base.update(plain)
    mapping = SealedRecord(**base).to_reveal_mapping()
    return mapping
