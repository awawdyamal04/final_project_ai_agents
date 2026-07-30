"""The tamper-evident audit log and its independent verifier."""

from __future__ import annotations

import json

import pytest

from police_thief.audit.chain import GENESIS_HASH, compute_record_hash
from police_thief.audit.exceptions import AuditPrivacyError
from police_thief.audit.records import (
    AUDIT_SCHEMA_VERSION,
    RECORD_KEYS,
    AuditEventType,
)
from police_thief.audit.verifier import (
    TAMPERED,
    VERIFIED_OK,
    load_records,
    verify_chain,
    verify_chain_file,
)
from police_thief.audit.writer import AuditLog


@pytest.fixture
def log(tmp_path) -> AuditLog:
    return AuditLog(path=tmp_path / "audit.jsonl", game_id="g1", role="police")


def populate(log: AuditLog, turns: int = 3) -> None:
    log.append(AuditEventType.SUB_GAME_START, {"grid": 7})
    for turn in range(1, turns + 1):
        log.append(
            AuditEventType.LOCAL_COMMIT, {"commitment": "a" * 64},
            turn_number=turn,
        )
        log.append(
            AuditEventType.OPPONENT_COMMIT, {"commitment": "b" * 64},
            turn_number=turn,
        )
        log.append(
            AuditEventType.LOCAL_REVEAL,
            {"sealed": {"action": {"v": 1, "kind": "move", "direction": "N"}}},
            turn_number=turn,
        )
    log.append(AuditEventType.SUB_GAME_END, {"reason": "survival"})


# ----------------------------------------------------------------------
# Writing and chaining
# ----------------------------------------------------------------------


def test_first_record_follows_the_explicit_genesis_hash(log):
    record = log.append(AuditEventType.SUB_GAME_START, {})
    assert record.previous_event_hash == GENESIS_HASH == "0" * 64


def test_record_key_set_is_closed_and_complete(log):
    record = log.append(AuditEventType.SUB_GAME_START, {})
    assert set(record.to_mapping()) == set(RECORD_KEYS)
    assert record.schema_version == AUDIT_SCHEMA_VERSION


def test_each_record_chains_to_its_predecessor(log):
    populate(log)
    records = load_records(log.path)
    for previous, current in zip(records, records[1:]):
        assert current["previous_event_hash"] == previous["current_event_hash"]


def test_hash_excludes_its_own_field(log):
    """A hash cannot cover itself."""
    record = log.append(AuditEventType.SUB_GAME_START, {"a": 1}).to_mapping()
    recomputed = compute_record_hash(record)
    assert recomputed == record["current_event_hash"]

    without = {k: v for k, v in record.items() if k != "current_event_hash"}
    assert compute_record_hash(without) == recomputed


def test_hashing_is_deterministic_and_canonical(log):
    record = log.append(AuditEventType.SUB_GAME_START, {"b": 2, "a": 1})
    mapping = record.to_mapping()
    reordered = dict(reversed(list(mapping.items())))
    assert compute_record_hash(reordered) == compute_record_hash(mapping)


def test_log_is_append_only(log):
    """No update, no delete, and the file is only ever opened for append."""
    populate(log)
    first_line = log.path.read_text(encoding="utf-8").splitlines()[0]

    log.append(AuditEventType.AUDIT_RESULT, {"result": "verified"})
    assert log.path.read_text(encoding="utf-8").splitlines()[0] == first_line

    for forbidden in ("update", "delete", "rewrite", "truncate", "edit"):
        assert not hasattr(log, forbidden)


def test_duplicate_event_id_is_refused_at_write_time(log):
    log.append(AuditEventType.SUB_GAME_START, {}, event_id="fixed")
    with pytest.raises(AuditPrivacyError, match="already used"):
        log.append(AuditEventType.SUB_GAME_END, {}, event_id="fixed")


# ----------------------------------------------------------------------
# Verification -- the clean case
# ----------------------------------------------------------------------


def test_a_clean_chain_verifies(log):
    populate(log)
    verdict = verify_chain_file(log.path)
    assert verdict
    assert verdict.stamp == VERIFIED_OK
    assert verdict.records_checked == log.count == 11


def test_an_empty_log_verifies(tmp_path):
    (tmp_path / "empty.jsonl").write_text("", encoding="utf-8")
    assert verify_chain_file(tmp_path / "empty.jsonl")


def test_missing_file_is_reported(tmp_path):
    verdict = verify_chain_file(tmp_path / "absent.jsonl")
    assert not verdict
    assert "no log at" in verdict.reason


# ----------------------------------------------------------------------
# Verification -- every tampering mode
# ----------------------------------------------------------------------


def test_modified_payload_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[3]["payload"]["commitment"] = "c" * 64

    verdict = verify_chain(records)
    assert not verdict
    assert verdict.stamp == TAMPERED
    assert verdict.failure_index == 3
    assert verdict.failure_kind == "AuditHashMismatchError"


def test_modified_timestamp_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[2]["timestamp"] = "2099-01-01T00:00:00.000+00:00"
    assert verify_chain(records).failure_kind == "AuditHashMismatchError"


def test_modified_turn_number_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[4]["turn_number"] = 99
    assert verify_chain(records).failure_kind == "AuditHashMismatchError"


def test_modified_event_type_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[1]["event_type"] = AuditEventType.TURN_FAILED.value
    assert verify_chain(records).failure_kind == "AuditHashMismatchError"


def test_deleted_middle_record_is_detected(log):
    """The record after the gap now points at a hash that is not in front."""
    populate(log)
    records = load_records(log.path)
    del records[5]

    verdict = verify_chain(records)
    assert not verdict
    assert verdict.failure_kind == "AuditChainBreakError"
    assert verdict.failure_index == 5


def test_inserted_record_is_detected(log):
    populate(log)
    records = load_records(log.path)
    forged = json.loads(json.dumps(records[2]))
    forged["event_id"] = "forged-id"
    records.insert(4, forged)

    verdict = verify_chain(records)
    assert not verdict
    assert verdict.failure_kind == "AuditChainBreakError"


def test_reordered_records_are_detected(log):
    populate(log)
    records = load_records(log.path)
    records[3], records[6] = records[6], records[3]
    assert verify_chain(records).failure_kind == "AuditChainBreakError"


def test_truncating_the_tail_still_verifies(log):
    """A prefix is a valid chain -- truncation removes evidence but does not
    forge it. Detecting a missing tail needs an external anchor, which is what
    the two-log mutual audit provides (E-36)."""
    populate(log)
    records = load_records(log.path)
    assert verify_chain(records[:5])


def test_duplicate_event_id_is_detected_on_read(log):
    populate(log)
    records = load_records(log.path)
    records[4]["event_id"] = records[2]["event_id"]
    verdict = verify_chain(records)
    assert verdict.failure_kind in (
        "DuplicateAuditEventError", "AuditHashMismatchError"
    )


def test_malformed_line_is_detected(log, tmp_path):
    populate(log)
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    verdict = verify_chain_file(log.path)
    assert not verdict
    assert verdict.failure_kind == "MalformedLine"


def test_wrong_previous_hash_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[3]["previous_event_hash"] = "0" * 64
    assert verify_chain(records).failure_kind in (
        "AuditChainBreakError", "AuditHashMismatchError"
    )


def test_wrong_current_hash_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[3]["current_event_hash"] = "d" * 64
    assert verify_chain(records).failure_kind == "AuditHashMismatchError"


def test_schema_violation_is_detected(log):
    populate(log)
    records = load_records(log.path)
    records[2]["extra_field"] = "surprise"
    assert verify_chain(records).failure_kind == "AuditRecordSchemaError"


def test_verifier_reports_the_first_failure_only(log):
    populate(log)
    records = load_records(log.path)
    records[3]["payload"]["x"] = 1
    records[7]["payload"]["y"] = 2
    assert verify_chain(records).failure_index == 3


def test_verdict_describes_itself(log):
    populate(log)
    assert VERIFIED_OK in verify_chain_file(log.path).describe()
    records = load_records(log.path)
    records[2]["turn_number"] = 42
    assert TAMPERED in verify_chain(records).describe()


# ----------------------------------------------------------------------
# Privacy schedule (E-18, E-9, E-39)
# ----------------------------------------------------------------------


def test_a_nonce_cannot_be_logged_before_the_final_reveal(log):
    """Logging the nonce alongside the commitment would defeat it entirely."""
    with pytest.raises(AuditPrivacyError, match="nonces are disclosed only"):
        log.append(
            AuditEventType.LOCAL_COMMIT,
            {"commitment": "a" * 64, "nonce": "b" * 32},
            turn_number=1,
        )


def test_a_nonce_nested_deep_is_still_refused(log):
    with pytest.raises(AuditPrivacyError):
        log.append(
            AuditEventType.LOCAL_REVEAL,
            {"sealed": [{"inner": {"nonce": "b" * 32}}]},
            turn_number=1,
        )


def test_the_final_reveal_may_carry_nonces(log):
    """The one event type where disclosure is correct (PDF p. 51)."""
    record = log.append(
        AuditEventType.FINAL_REVEAL,
        {"records": [{"turn": 1, "nonce": "b" * 32}]},
    )
    assert record.payload["records"][0]["nonce"] == "b" * 32


@pytest.mark.parametrize(
    "forbidden",
    ["client_secret", "refresh_token", "credentials_path",
     "opponent_position", "global_state", "board_state"],
)
def test_secrets_and_global_state_are_refused(log, forbidden):
    with pytest.raises(AuditPrivacyError, match="forbidden key"):
        log.append(AuditEventType.SUB_GAME_START, {forbidden: "x"})


def test_pre_reveal_log_contains_no_action_or_nonce(log):
    """The whole commit phase, inspected."""
    log.append(
        AuditEventType.LOCAL_COMMIT, {"commitment": "a" * 64}, turn_number=1
    )
    log.append(
        AuditEventType.OPPONENT_COMMIT, {"commitment": "b" * 64}, turn_number=1
    )
    text = log.path.read_text(encoding="utf-8")

    assert "nonce" not in text
    assert '"direction"' not in text
    assert "place_barrier" not in text
