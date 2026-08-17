"""Full pipeline: ``replay_logs`` -> ``_reconstruct`` -> ``check_capture_claims``
(E-21, E-22). Split out of ``test_capture_claim_check.py`` purely to stay
under the 150-line lecturer limit."""

from __future__ import annotations

import copy
import json

from police_thief.audit.capture_claim_records import claim_payload, response_payload
from police_thief.audit.records import AuditEventType
from police_thief.audit.writer import AuditLog
from police_thief.protocol.capture_claim import (
    VERDICT_CONFIRM,
    CaptureClaim,
    CaptureClaimResponse,
)
from police_thief.replay.verifier import Verdict, replay_logs
from tests.replay.test_two_log_replay import cfg, real_logs  # noqa: F401  (fixtures)


async def test_replay_pipeline_flags_a_false_confirmed_claim(real_logs, cfg, tmp_path):  # noqa: F811
    """D-41 augmented: a real, otherwise-valid survival game (no capture at
    all) into which a confirmed capture_claim is injected must now come back
    TAMPERED -- proving the hook in ``replay/verifier.py`` actually runs."""
    cop, thief = real_logs

    cop_log = AuditLog(tmp_path / "cop2.jsonl", game_id="test-game", role="police")
    for record in cop:
        payload = record["payload"]
        if record["event_type"] == "sub_game_start":
            cop_log.append(AuditEventType.SUB_GAME_START, payload)
            cop_log.append(
                AuditEventType.CAPTURE_CLAIM,
                claim_payload(
                    CaptureClaim(
                        claim_id="injected", sub_game=1, turn=5,
                        claim_kind="barrier_on_thief", commitment="a" * 64,
                    ),
                    claimant_role="police",
                ),
                turn_number=5,
            )
            continue
        cop_log.append(
            AuditEventType(record["event_type"]), payload,
            turn_number=record["turn_number"],
        )
    cop_rebuilt = [json.loads(line) for line in cop_log.path.read_text().splitlines()]

    thief_log = AuditLog(tmp_path / "thief2.jsonl", game_id="test-game", role="thief")
    for record in thief:
        payload = record["payload"]
        if record["event_type"] == "sub_game_start":
            thief_log.append(AuditEventType.SUB_GAME_START, payload)
            thief_log.append(
                AuditEventType.CAPTURE_CLAIM_RESPONSE,
                response_payload(
                    CaptureClaimResponse(
                        claim_id="injected", sub_game=1, turn=5,
                        verdict=VERDICT_CONFIRM, commitment="b" * 64,
                    ),
                    responder_role="thief",
                ),
                turn_number=5,
            )
            continue
        thief_log.append(
            AuditEventType(record["event_type"]), payload,
            turn_number=record["turn_number"],
        )
    thief_rebuilt = [
        json.loads(line) for line in thief_log.path.read_text().splitlines()
    ]

    verdict = replay_logs(cop_rebuilt, thief_rebuilt, cfg)
    assert verdict.verdict is Verdict.TAMPERED
    assert "injected" in verdict.reason


async def test_replay_pipeline_agrees_when_no_claims_were_made(real_logs, cfg):  # noqa: F811
    """No claims at all -- the augmentation is silent, D-41's own path is
    unaffected (regression guard for requirement 8)."""
    cop, thief = real_logs
    verdict = replay_logs(copy.deepcopy(cop), copy.deepcopy(thief), cfg)
    assert verdict.verdict is Verdict.VERIFIED_OK
