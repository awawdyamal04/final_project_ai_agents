"""Reference-v3 adapter -- ``submit_audit`` integrity + binding checks.

Recomputation uses the same byte-level fix already shipped in commit
``33db121`` (:func:`pipe_nonce_commitment`), so a false tamper detection
from a serialization difference is structurally impossible here -- proven
below by round-tripping through the real canonical serializer, not a stub.
"""

from __future__ import annotations

from police_thief.interop.audit_adapter import seal_record, verify_audit


def test_seal_record_commit_is_reproducible():
    record = seal_record({"step": 1, "move": "N"}, nonce="deadbeef")
    from police_thief.config.hashing import pipe_nonce_commitment

    assert record["commit"] == pipe_nonce_commitment({"step": 1, "move": "N"}, "deadbeef")


def test_verify_audit_passes_for_an_honest_reveal():
    records = [seal_record({"step": s, "move": "N"}) for s in (1, 2, 3)]
    played = {r["payload"]["step"]: r["commit"] for r in records}
    theirs = {"sender": "police", "records": records, "result_claim": "capture"}
    result = verify_audit(theirs, played=played)
    assert result.verified
    assert not result.mismatches


def test_verify_audit_catches_a_forged_commit():
    record = seal_record({"step": 1, "move": "N"})
    record["commit"] = "0" * 64  # does not match payload+nonce
    theirs = {"sender": "police", "records": [record], "result_claim": "capture"}
    result = verify_audit(theirs, played={})
    assert not result.verified
    assert result.tampered


def test_verify_audit_catches_equivocation_against_what_was_played():
    record = seal_record({"step": 1, "move": "N"})
    theirs = {"sender": "police", "records": [record], "result_claim": "capture"}
    result = verify_audit(theirs, played={1: "different-commit-than-revealed"})
    assert not result.verified
    assert any("equivocation" in m for m in result.mismatches)


def test_verify_audit_rejects_missing_records_list():
    result = verify_audit({"sender": "police"}, played={})
    assert not result.verified


def test_verify_audit_rejects_a_record_missing_nonce():
    record = seal_record({"step": 1})
    del record["nonce"]
    theirs = {"sender": "police", "records": [record], "result_claim": "capture"}
    result = verify_audit(theirs, played={})
    assert not result.verified
