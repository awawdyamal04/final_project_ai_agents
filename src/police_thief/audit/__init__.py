"""Tamper-evident audit log.

Distinct from ``peer/events.py``, which is operational telemetry. This is the
cryptographic record: append-only JSON Lines, each entry hash-chained to its
predecessor, so that any modification, deletion, insertion or reordering of a
past entry is detectable by recomputation alone.

Ch. 7 (PDF p. 72) states the purpose: the replay viewer's *"distinctive feature
is not the graphical display but the cryptographic verification"*, and any
alteration of past data produces a red ``TAMPERED`` banner and immediate
disqualification of the match (E-19, E-20).

Phase 3 delivers the chain and its verifier. The full two-log game replay --
reconstructing both trajectories and checking captures -- is Phase 6.
"""

from police_thief.audit.chain import (
    GENESIS_HASH,
    compute_record_hash,
    hash_input_mapping,
)
from police_thief.audit.records import (
    AUDIT_SCHEMA_VERSION,
    AuditEventType,
    AuditRecord,
)
from police_thief.audit.verifier import (
    ChainVerdict,
    verify_chain,
    verify_chain_file,
)
from police_thief.audit.writer import AuditLog

__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "GENESIS_HASH",
    "AuditEventType",
    "AuditLog",
    "AuditRecord",
    "ChainVerdict",
    "compute_record_hash",
    "hash_input_mapping",
    "verify_chain",
    "verify_chain_file",
]
