"""Cross-team interop audit -- delivery contract (PROMOTED) and pairing
declaration (PROMOTED). Behaviour, not bytes, so these are exercised as
decision tables against this project's real ``CommitRevealCoordinator``
rather than compared to a hash.

Delivery contract (``vectors/delivery_contract.json``): a redelivered commit
for an already-played step must ABSORB silently; a *different* commit for
that step is equivocation and must stay loud. This project's
``record_opponent_commit`` does exactly that. Out-of-order buffering
(window > 0) is not implemented -- any arrival ahead of the current turn is
an immediate hard error, which matches the vector's own ``window: 0`` row
(a legal, if strict, choice: "zero tolerance is not a tightening here").

Pairing declaration (``vectors/pairing_declaration.json``): this project has
no negotiate-time ``sub_game_number``/``role`` exchange, but achieves the
same refusal outcomes structurally and earlier in most cases -- a role
collision is caught on the very first envelope
(``peer/orchestrator.py::_check_identity``, not exercised here directly; a
full orchestrator is out of scope for a unit test) and a sub-game mismatch
is caught on the first reveal (``accept_opponent_reveal`` below).
"""

from __future__ import annotations

import pytest

from police_thief.crypto.coordinator import CommitRevealCoordinator
from police_thief.crypto.exceptions import (
    ConflictingCommitError,
    InvalidRevealError,
)
from police_thief.crypto.sealed import SealedRecord
from police_thief.domain.actions import Move
from police_thief.domain.enums import Direction, Role


def _coordinator(role: Role = Role.POLICE, sub_game: int = 1) -> CommitRevealCoordinator:
    coord = CommitRevealCoordinator(game_id="g1", role=role, sub_game=sub_game)
    coord.begin_turn(1)
    return coord


def test_redelivered_identical_commit_absorbs_silently():
    coord = _coordinator()
    assert coord.record_opponent_commit(1, "c" * 64) is True
    assert coord.record_opponent_commit(1, "c" * 64) is False  # absorbed, no error


def test_a_different_commit_for_an_already_committed_turn_is_equivocation():
    coord = _coordinator()
    coord.record_opponent_commit(1, "c" * 64)
    with pytest.raises(ConflictingCommitError):
        coord.record_opponent_commit(1, "d" * 64)


def test_out_of_order_arrival_is_a_hard_violation_not_a_buffer():
    """Matches the vector's own ``window: 0`` row: no reorder buffering is
    implemented, so an ahead-of-turn arrival is refused outright rather
    than held and replayed in order."""
    coord = _coordinator()
    from police_thief.crypto.exceptions import FutureTurnMessageError

    with pytest.raises(FutureTurnMessageError):
        coord.begin_turn(2)  # turn 1 still open; this is "one ahead"


def _committed_both_sides(role: Role, sub_game: int) -> CommitRevealCoordinator:
    """A coordinator with both a local seal and an opponent commit in place
    -- the precondition ``accept_opponent_reveal`` requires before it will
    even look at the reveal's own sub-game/role claims."""
    coord = _coordinator(role=role, sub_game=sub_game)
    coord.seal(turn=1, action=Move(Direction.STAY), hint="", intent="truth",
               state_hash="0" * 64)
    coord.record_opponent_commit(1, "c" * 64)
    return coord


def test_sub_game_mismatch_is_refused_on_the_first_reveal():
    """The pairing-declaration outcome ('sub-game numbers differ -> refuse')
    achieved structurally: a reveal claiming the wrong sub-game is rejected
    where this project checks it, one layer down from a negotiate-time
    declaration but before any turn state is trusted."""
    ours = _committed_both_sides(role=Role.POLICE, sub_game=3)
    theirs_wrong_subgame = SealedRecord(
        game_id="g1", sub_game=5, turn=1, role=Role.THIEF, state="a" * 64,
        action=Move(Direction.N), hint="", intent="truth", nonce="0" * 32,
    )
    with pytest.raises(InvalidRevealError, match="sub-game"):
        ours.accept_opponent_reveal(1, theirs_wrong_subgame.to_reveal_mapping())


def test_role_collision_is_refused_on_the_first_reveal():
    """Both sides declaring the same role can only deadlock; this project's
    reveal path already rejects a reveal claiming the wrong role."""
    ours = _committed_both_sides(role=Role.POLICE, sub_game=1)
    theirs_wrong_role = SealedRecord(
        game_id="g1", sub_game=1, turn=1, role=Role.POLICE, state="a" * 64,
        action=Move(Direction.N), hint="", intent="truth", nonce="0" * 32,
    )
    with pytest.raises(InvalidRevealError, match="role"):
        ours.accept_opponent_reveal(1, theirs_wrong_role.to_reveal_mapping())
