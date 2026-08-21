"""Structural validation of an inbound reference-v3 ``TurnMessage``.

Every case here mirrors ``vectors/turn_message.json``'s ``validation`` list
byte-for-byte: missing required keys are refused (never defaulted -- a
defaulted ``commit`` would be a move the sender never sealed), unknown keys
are tolerated (the extension seam), and every check runs **before** any state
change (that file's own ``validate_before_applying`` note: under App. E rule
35 a self-inflicted protocol fault zeroes both teams, so a partially applied
bad turn must never happen).
"""

from __future__ import annotations

import re
from typing import Any

from police_thief.interop.exceptions import TurnValidationError
from police_thief.interop.wire import TURN_REQUIRED

_COMMIT_RE = re.compile(r"^[0-9a-f]{64}$")
_SENDERS = frozenset({"police", "thief"})


def validate_turn_message(raw: Any) -> dict[str, Any]:
    """Raise :class:`TurnValidationError` on the first violation found, in
    the same key order the vector checks it, otherwise return ``raw``
    unchanged (unknown keys included -- the receiver ignores, not strips)."""
    if not isinstance(raw, dict):
        raise TurnValidationError(f"turn message must be an object, got {type(raw).__name__}")

    missing = sorted(TURN_REQUIRED - set(raw))
    if missing:
        raise TurnValidationError(f"missing required field(s): {missing}")

    _check_step(raw["step"])
    _check_sender(raw["sender"])
    _check_hint(raw["hint"])
    _check_smell_grid(raw["smell_grid"])
    _check_commit(raw["commit"])
    _check_timestamp(raw["timestamp"])
    _check_optional_cell("barrier_placed", raw.get("barrier_placed"))
    _check_optional_cell("capture_claim", raw.get("capture_claim"))
    return raw


def _check_step(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TurnValidationError("step: required non-negative int")
    if value < 0:
        raise TurnValidationError("step: required non-negative int")


def _check_sender(value: Any) -> None:
    if value not in _SENDERS:
        raise TurnValidationError(f"sender: must be one of {sorted(_SENDERS)}, got {value!r}")


def _check_hint(value: Any) -> None:
    if not isinstance(value, str):
        raise TurnValidationError(f"hint: required str, got {type(value).__name__}")


def _check_smell_grid(value: Any) -> None:
    if not isinstance(value, dict):
        raise TurnValidationError("smell_grid: required dict of 'r,c' -> number")
    for key, intensity in value.items():
        if not isinstance(key, str):
            raise TurnValidationError("smell_grid: required dict of 'r,c' -> number")
        if isinstance(intensity, bool) or not isinstance(intensity, int | float):
            raise TurnValidationError("smell_grid: required dict of 'r,c' -> number")


def _check_commit(value: Any) -> None:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise TurnValidationError("commit: required 64-char lowercase hex")


def _check_timestamp(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise TurnValidationError("timestamp: required non-empty str")


def _check_optional_cell(name: str, value: Any) -> None:
    if value is None:
        return
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(isinstance(c, bool) or not isinstance(c, int) for c in value)
    ):
        raise TurnValidationError(f"{name}: must be a [row, col] pair of ints or null")
