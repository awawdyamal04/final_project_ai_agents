"""The hash chain.

Each record's hash covers the previous record's hash plus its own contents,
which is what makes the log tamper-evident: altering any past record changes
its hash, so every record after it now points at something that no longer
exists.

Formula
-------
::

    hash_input   = canonical_json_bytes(record_without_current_event_hash)
    current_hash = SHA256(hash_input)

``current_event_hash`` is excluded from its own input -- a hash cannot cover
itself. ``previous_event_hash`` *is* included, and that inclusion is the chain:
it is the only reason a change in record 3 invalidates record 4.

The genesis predecessor is 64 zeros, stated explicitly rather than left as an
empty string, so the first record is verified by the same code path as every
other one.

Serialisation goes through the single project canonical helper, the same one
used for the config hash and the commitment. Byte-identical hashing on both
peers is the whole basis of mutual audit (Ch. 5, PDF p. 50).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from police_thief.config.canonical import canonical_json_bytes
from police_thief.config.hashing import sha256_hex

GENESIS_HASH = "0" * 64
"""The predecessor of the first record. Explicit, so record 1 is not a special
case in the verifier."""


def hash_input_mapping(record: Mapping[str, Any]) -> dict[str, Any]:
    """The record minus its own hash -- exactly what gets hashed."""
    return {k: v for k, v in record.items() if k != "current_event_hash"}


def compute_record_hash(record: Mapping[str, Any]) -> str:
    """``SHA256(canonical_json_bytes(record without current_event_hash))``."""
    return sha256_hex(canonical_json_bytes(hash_input_mapping(record)))
