"""Enumerations shared across the project.

Values here are structural (they name things), not quantitative. Every
quantitative value comes from configuration -- see config/policy.py.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """The two peer roles.

    The PDF names the sides שוטר (cop/police) and גנב (thief). The reference
    implementation's private-config keys are ``police_class`` and
    ``thief_class`` (Appendix F table 22, PDF p. 159), so ``police`` is the
    canonical spelling for the cop role on the wire and in config.
    """

    POLICE = "police"
    THIEF = "thief"

    @property
    def opponent(self) -> Role:
        return Role.THIEF if self is Role.POLICE else Role.POLICE


class ParameterStatus(str, Enum):
    """The three -- and only three -- statuses used by Appendix F.

    PDF p. 155 states it directly: "the status column in the tables above
    receives one of three values". There is no DEFAULT status and no OPTIONAL
    status; inventing either would be inventing a category.
    """

    FIXED = "fixed"
    """קבוע -- binding, not changeable at all. Deviation disqualifies the team."""

    MINIMUM = "minimum"
    """מינימום -- negotiable only in the direction that makes the game harder;
    never eased below the tabulated value."""

    NEGOTIABLE = "negotiable"
    """משא ומתן -- the sides may agree on any value."""


class Direction(str, Enum):
    """The orthogonal directions plus standing still.

    These are the tokens of ``move_set``, which Appendix F fixes at
    ``["N", "S", "E", "W", "STAY"]`` (table 15 row 1, FIXED). Diagonals are
    forbidden (E-13, E-14) and deliberately have no representation here -- an
    illegal move should be unspeakable, not merely rejected.

    ``delta`` assumes the default axis convention: origin top-left with the
    vertical axis growing downward (Ch. 3, PDF p. 34), so ``N`` decreases the
    row. Figure 3 on PDF p. 36 draws row 0 at the bottom, but diagrams are not
    binding (PDF p. 4) -- see OPEN_QUESTIONS.md Q-10. Under a different agreed
    ``axis_origin_corner`` the deltas are reinterpreted by the board, not here.
    """

    N = "N"
    S = "S"
    E = "E"
    W = "W"
    STAY = "STAY"

    @property
    def delta(self) -> tuple[int, int]:
        return _DIRECTION_DELTAS[self]

    @property
    def is_relocation(self) -> bool:
        """True for the four directions that change the occupied cell.

        E-47 defines a trapped thief as one whose *adjacent cells* are all
        blocked; ``STAY`` does not rescue it. Distinguishing relocation from
        standing still is what makes that rule expressible.
        """
        return self is not Direction.STAY


_DIRECTION_DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.N: (-1, 0),
    Direction.S: (1, 0),
    Direction.E: (0, 1),
    Direction.W: (0, -1),
    Direction.STAY: (0, 0),
}

ORTHOGONAL_DIRECTIONS: tuple[Direction, ...] = (
    Direction.N,
    Direction.S,
    Direction.E,
    Direction.W,
)
"""The four relocations, in a fixed order.

Order matters: legal-action generation must be deterministic so two peers
enumerate identically and a test can assert on the sequence.
"""


class ActionKind(str, Enum):
    """What a peer does on its turn.

    Barrier placement is a first-class action rather than a flag on a move,
    because the PDF makes it an alternative *to* moving: "on a turn where the cop
    forgoes movement, it may place a barrier" (PDF p. 37). Encoding it as a side
    effect of a move would misrepresent the rule.
    """

    MOVE = "move"
    PLACE_BARRIER = "place_barrier"


class TerminalReason(str, Enum):
    """Why a sub-game ended.

    The PDF's scoring table (Ch. 3 table 2, PDF p. 38) has three outcomes:
    capture, prolonged survival, technical loss. ``MAX_MOVES_REACHED`` is a
    defensive fourth: Phase 0 validation guarantees
    ``survival_threshold <= max_moves``, so survival always fires first, but a
    loop bound that can be reached without a reason is a silent hang waiting to
    happen.
    """

    CAPTURE = "capture"
    SURVIVAL = "survival"
    TECHNICAL_LOSS = "technical_loss"
    MAX_MOVES_REACHED = "max_moves_reached"


class CaptureReason(str, Enum):
    """How the thief was caught. All three are mandatory."""

    COP_LANDED_ON_THIEF = "cop_landed_on_thief"
    """Ch. 3 scoring table (PDF p. 38): the cop lands on the thief's cell."""

    BARRIER_ON_THIEF = "barrier_on_thief"
    """E-46 (PDF p. 149): a barrier placed on the cell where the thief stands
    counts as a capture at that moment."""

    THIEF_HAS_NO_LEGAL_MOVE = "thief_has_no_legal_move"
    """E-47 (PDF p. 149): a thief imprisoned with no legal move -- all adjacent
    cells blocked by barriers and/or board edges -- is likewise captured."""


class AxisOriginCorner(str, Enum):
    """Which corner holds cell (0,0).

    Appendix F table 13 row 3 tabulates ``top-left`` and marks the parameter
    NEGOTIABLE. The PDF names only that one corner; the remaining three are the
    natural completion of "the corner in which cell (0,0) sits" and are accepted
    so a negotiated layout is not rejected out of hand.
    """

    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"


class VerbalProvider(str, Enum):
    """How the deception text is produced (Appendix F table 21, PDF p. 158).

    A private per-peer choice, never negotiated. All four modes touch only the
    verbal layer -- the move is always decided in Python.
    """

    TEMPLATE = "template"
    """Zero tokens, offline, the PDF's default."""

    OLLAMA = "ollama"
    CLAUDE_API = "claude_api"
    CLAUDE_CLI = "claude_cli"


class EmailMode(str, Enum):
    """Reporting mode.

    ``send`` is the default and the only mode permitted for a counting league
    match (E-32, E-51; see DECISIONS.md D-5). ``draft`` exists purely as a
    development convenience.
    """

    SEND = "send"
    DRAFT = "draft"
