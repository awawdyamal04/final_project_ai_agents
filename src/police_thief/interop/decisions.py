"""Small refusal decision tables shared by negotiation (SPEC section 7,
7.2, 7.3). One rule underlies all three: **omission never refuses, in
either direction** -- the unmodified reference peer declares none of these
fields, and a guard that fail-fasts on silence forfeits the game to itself.
"""

from __future__ import annotations

from typing import Any


def lock_decision(ours: str | None, theirs: str | None) -> str:
    """Refuse only when both sides declare a value and it differs. Used for
    the four locked-model families (section 7) and the ``game_uid``
    declaration (section 7.3), which shares the same rule."""
    if ours is None or theirs is None:
        return "play"
    return "play" if ours == theirs else "refuse"


def pairing_decision(
    ours_sub_game: int | None, ours_role: str | None, raw: dict[str, Any]
) -> str:
    """Sub-game mismatch or role collision refuses (section 7.2); a value
    that cannot be compared is treated as silence."""
    theirs_sg = raw.get("sub_game_number")
    if isinstance(ours_sub_game, int) and isinstance(theirs_sg, int) and ours_sub_game != theirs_sg:
        return "refuse:sub_game"
    theirs_role = raw.get("role")
    if isinstance(ours_role, str) and isinstance(theirs_role, str) and ours_role == theirs_role:
        return "refuse:role"
    return "play"
