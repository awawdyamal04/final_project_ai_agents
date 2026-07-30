"""Bounded message registry: idempotency and duplicate detection.

The network may deliver a message twice, and a retry after a lost *response* is
indistinguishable from a duplicate *request*. Both must be safe.

Three outcomes, and the third is the interesting one:

* **Exact duplicate** -- same id, same payload. Return the cached reply. The
  work is not redone.
* **Stale or evicted** -- the id is beyond the bound. Treated as new.
* **Conflicting duplicate** -- same id, *different* payload. Rejected and
  logged. This is the signature of an attempt to change a decision after the
  fact, which is exactly what commit-reveal exists to prevent (Ch. 5,
  PDF p. 49). Silently accepting the second version would discard the evidence.

Bounded by ``queue_depth`` from the shared configuration, evicting
least-recently-inserted first. An unbounded registry is a memory leak that a
long league series would eventually find.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Mapping

from police_thief.config.canonical import canonical_json_bytes
from police_thief.protocol.exceptions import ConflictingDuplicateError


@dataclass(frozen=True, slots=True)
class RegistryHit:
    """A previously-seen message and the reply we gave it."""

    message_id: str
    response: Mapping[str, Any]


class MessageRegistry:
    """Fixed-capacity record of handled message ids.

    Not thread-safe by design: it is owned by a single peer's event loop, and
    adding a lock would imply a concurrency model this package does not have.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("registry capacity must be at least 1")
        self._capacity = capacity
        self._entries: OrderedDict[str, tuple[bytes, Mapping[str, Any]]] = (
            OrderedDict()
        )
        self.evictions = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, message_id: str) -> bool:
        return message_id in self._entries

    def lookup(
        self, message_id: str, payload: Mapping[str, Any]
    ) -> RegistryHit | None:
        """Return the cached reply for an exact duplicate, else ``None``.

        Raises :class:`ConflictingDuplicateError` when the id was seen with a
        different payload.

        Comparison is by canonical bytes, not by ``==`` on the mapping: two
        payloads that differ only in key order are the same message, and
        treating them as a conflict would reject legitimate retries from a peer
        whose JSON library orders keys differently from ours.
        """
        entry = self._entries.get(message_id)
        if entry is None:
            return None

        stored_fingerprint, response = entry
        if _fingerprint(payload) != stored_fingerprint:
            raise ConflictingDuplicateError(
                f"message id {message_id!r} was already used with a different "
                f"payload; reusing an id to change a decision is exactly what "
                f"the commitment scheme exists to prevent"
            )
        return RegistryHit(message_id=message_id, response=response)

    def record(
        self,
        message_id: str,
        payload: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> None:
        """Store the reply given to ``message_id``, evicting if full."""
        self._entries[message_id] = (_fingerprint(payload), dict(response))
        self._entries.move_to_end(message_id)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)
            self.evictions += 1

    def clear(self) -> None:
        self._entries.clear()


def _fingerprint(payload: Mapping[str, Any]) -> bytes:
    """Canonical bytes of a payload, for order-insensitive comparison."""
    return canonical_json_bytes(dict(payload))
