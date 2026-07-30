"""Resolution of simultaneous-movement edge cases.

**The PDF does not resolve any of this.** It never states whether the cop or the
thief moves first (OPEN_QUESTIONS.md Q-2), and it never addresses what happens
when the two agents interact within one turn (Q-9). What it *does* fix is that
scent decay is applied "at the end of each full turn -- after both the cop and
the thief have completed their move" (Ch. 4, PDF p. 43), which makes turns
paired rather than interleaved but says nothing about resolution.

Rather than pick an answer and bury it in the capture logic, every such case is
isolated behind :class:`SimultaneityPolicy`. Swapping the policy changes the
outcome without touching anything else, and the unresolved cases are visible in
one file instead of being implicit in a comparison somewhere.

**This must be agreed with each opponent before a counting match.** Two peers
running different policies will disagree about whether a capture occurred, and
that disagreement surfaces as a failed audit costing *both* sides the match
(E-19, E-35) -- not as a polite error message.

The four open cases
-------------------
1. **Cell swap.** Cop A→B while thief B→A. Post-move positions differ.
2. **Vacated cell.** Cop moves onto the cell the thief just left.
3. **Same target.** Both move to the same empty cell.
4. **Thief moves onto the cop.** Ch. 3 phrases capture as *the cop* landing on
   the thief (PDF p. 38). Whether the mirror image counts is not stated.

Case 3 is the only one where every reading agrees: the two end up on the same
cell, and post-move coincidence is a capture under any interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import CaptureReason


@dataclass(frozen=True, slots=True)
class TurnMovement:
    """Where both agents were and where they ended up, for one full turn.

    Constructed only by an adjudicator that legitimately holds both positions:
    the Phase 1 test harness, or the post-match replay verifier. A live peer
    never builds one, because a live peer never has the inputs.
    """

    cop_before: Coordinate
    cop_after: Coordinate
    thief_before: Coordinate
    thief_after: Coordinate

    @property
    def is_swap(self) -> bool:
        return (
            self.cop_after == self.thief_before
            and self.thief_after == self.cop_before
            and self.cop_before != self.thief_before
        )

    @property
    def cop_entered_vacated_cell(self) -> bool:
        return (
            self.cop_after == self.thief_before
            and self.thief_after != self.thief_before
            and not self.is_swap
        )

    @property
    def positions_coincide(self) -> bool:
        return self.cop_after == self.thief_after


class SimultaneityPolicy(Protocol):
    """Decides whether a full turn's movement produced a capture."""

    name: str

    def resolve(self, movement: TurnMovement) -> CaptureReason | None:
        """Return a capture reason, or ``None`` if no capture occurred."""
        ...


@dataclass(frozen=True, slots=True)
class PostMovePositionsOnly:
    """Capture iff the two agents end the turn on the same cell.

    This implements DECISIONS.md D-7, and it is **our reading, not the PDF's
    ruling**. Chapter 3 defines capture as the cop "landing on" the thief's cell
    (PDF p. 38), which reads most naturally as post-move coincidence.

    Consequences, each of which an opponent might reasonably dispute:

    * a **swap** is not a capture -- the two pass through each other;
    * entering a **vacated** cell is not a capture -- the thief has already left;
    * a **same-target** collision is a capture;
    * the thief moving onto the cop **is** a capture, because coincidence is
      symmetric even though the PDF's phrasing is cop-centric.

    The last is the least defensible of the four and the one most worth raising
    in negotiation: it means a thief can lose by blundering into the cop, which
    the PDF never says.
    """

    name: str = "post_move_positions_only"

    def resolve(self, movement: TurnMovement) -> CaptureReason | None:
        if movement.positions_coincide:
            return CaptureReason.COP_LANDED_ON_THIEF
        # TODO(Q-9): a swap and a vacated-cell entry are treated as misses here.
        # Both are unresolved by the PDF and must be agreed with the opponent
        # before a counting match; an opponent reading them as captures will
        # produce a different match outcome from identical move sequences.
        return None


BLOCKED_MOVE_BECOMES_STAY = "blocked_move_becomes_stay"
"""**UNRESOLVED (Q-18). Test-harness rule only -- not final.**

A fifth collision the PDF does not address, found while running full games: the
cop places a barrier on the very cell the thief had already chosen to move into.
Both chose from the same pre-turn board, so neither did anything illegal, yet
one of the two actions cannot be carried out.

Readings, none excluded by the text:

1. the thief's move fails and it stays put (what the harness does, so a game
   can finish);
2. the thief's move succeeds, the barrier landing behind it;
3. the barrier placement fails, having been pre-empted;
4. the collision is a capture, the thief having been sealed in mid-step.

Reading 1 is used **only** by the sequential test harness, and only because a
demonstration needs to terminate. It is not a ruling. A real match must agree
one of these in negotiation before play -- two peers applying different readings
would compute different boards from identical action sequences, and that
surfaces as a failed audit costing both sides the match.
"""


DEFAULT_SIMULTANEITY_POLICY: SimultaneityPolicy = PostMovePositionsOnly()
"""The policy used unless an adjudicator is given another.

Named a *default*, not a *rule*: the PDF supplies no rule here.
"""
