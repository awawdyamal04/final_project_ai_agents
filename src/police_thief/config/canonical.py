"""Canonical JSON serialisation.

**This is the only serialisation implementation in the project.** Config
hashing, commit-reveal sealing, event-log hashing and report artefacts all call
it. Two implementations would eventually disagree, and the failure mode is not a
crash -- it is a failed audit in a real match, costing both sides the game
(E-19). If you find yourself reaching for ``json.dumps`` elsewhere, call this
instead.

The PDF requires it (Ch. 5, PDF pp. 50-51): concatenation for the commitment
hash is performed via canonical JSON serialisation -- *sorted keys and fixed
separators* -- so that both peers hash byte-identical input. Appendix B
(PDF p. 127) gives the same reason for choosing JSON for the shared config: it
is canonically serialisable and therefore suited to byte-for-byte identity and
to a consistent ``config_sha256``.

Canonical form:

* object keys sorted by Unicode code point;
* separators ``","`` and ``":"`` with no whitespace;
* UTF-8, emitted as real characters rather than ``\\uXXXX`` escapes;
* no NaN or Infinity (they are not valid JSON and are not portable);
* nothing added -- no timestamps, no version stamps, no ordering hints.
"""

from __future__ import annotations

import json
from typing import Any

from police_thief.config.exceptions import CanonicalSerialisationError

# bool is a subclass of int, so it must be tested before int everywhere below.
_ALLOWED_SCALARS = (str, bool, int, float, type(None))


def _reject_unsupported(value: Any, path: str = "$") -> None:
    """Walk the value and raise on anything not deterministically serialisable.

    ``json.dumps`` would happily accept a tuple (as an array) or coerce nothing
    at all for a set. Rejecting explicitly means an unsupported type surfaces at
    the call site with a path, instead of producing bytes that differ from what
    the other peer produced from the "same" data.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalSerialisationError(
                    f"{path}: object keys must be strings, got "
                    f"{type(key).__name__} ({key!r})"
                )
            _reject_unsupported(item, f"{path}.{key}")
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_unsupported(item, f"{path}[{index}]")
        return

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return

    if isinstance(value, int):
        return

    if isinstance(value, float):
        # NaN and +/-Infinity have no JSON representation. json.dumps would emit
        # the bare tokens NaN/Infinity, which most parsers reject.
        if value != value or value in (float("inf"), float("-inf")):
            raise CanonicalSerialisationError(
                f"{path}: {value!r} has no canonical JSON representation"
            )
        return

    raise CanonicalSerialisationError(
        f"{path}: {type(value).__name__} is not canonically serialisable "
        f"(allowed: dict, list, str, int, float, bool, None)"
    )


def canonical_json_text(value: Any) -> str:
    """Return the canonical JSON text for ``value``.

    Deterministic: the same semantic value always produces the same string,
    regardless of the order keys were inserted in or how the source file was
    whitespaced.
    """
    _reject_unsupported(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON bytes for ``value`` (UTF-8).

    This is what gets hashed. Always hash the bytes, never the text -- hashing a
    ``str`` requires an encoding decision, and making that decision twice is how
    two peers end up with different digests for identical data.
    """
    return canonical_json_text(value).encode("utf-8")
