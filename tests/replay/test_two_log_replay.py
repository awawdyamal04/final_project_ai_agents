"""Two-log replay verification, against real logs and tampered copies."""

from __future__ import annotations

import ast
import asyncio
import copy
import json
from pathlib import Path

import pytest

from police_thief.audit.writer import AuditLog
from police_thief.config.loader import build_shared_config, load_shared_config
from police_thief.domain.actions import Move
from police_thief.domain.enums import Direction
from police_thief.replay.verifier import Verdict, replay_files, replay_logs
from police_thief.replay.viewer import render
from tests.conftest import SHARED_CONFIG_PATH
from tests.peer.conftest import build_peer
from tests.peer.test_crypto_turn import play_together
from tests.peer.test_orchestrator import drive_to_ready


@pytest.fixture
def cfg():
    return load_shared_config(SHARED_CONFIG_PATH)


async def _play(shared, cop_private, thief_private, tmp_path, turns, *, finish):
    """Play a sub-game with the real strategies and return both logs.

    ``finish=False`` leaves out the final reveal, producing a log that is
    internally consistent but genuinely unfinished -- which is a different
    thing from a log somebody edited.
    """
    from police_thief.audit.records import AuditEventType

    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server
    cop.orchestrator.audit = AuditLog(
        tmp_path / "cop.jsonl", game_id="test-game", role="police"
    )
    thief.orchestrator.audit = AuditLog(
        tmp_path / "thief.jsonl", game_id="test-game", role="thief"
    )

    await drive_to_ready(cop, thief)
    for turn in range(1, turns + 1):
        # No explicit action: each peer's own strategy chooses, so every move
        # is legal by construction however long the game runs.
        await asyncio.gather(
            cop.orchestrator.play_turn(turn),
            thief.orchestrator.play_turn(turn),
        )

    if finish:
        for peer in (cop, thief):
            peer.orchestrator.audit.append(
                AuditEventType.FINAL_REVEAL,
                peer.orchestrator.crypto.final_reveal_payload(),
            )
            peer.orchestrator.close_sub_game()

    return (
        [json.loads(l) for l in (tmp_path / "cop.jsonl").read_text().splitlines()],
        [json.loads(l) for l in (tmp_path / "thief.jsonl").read_text().splitlines()],
    )


@pytest.fixture
async def real_logs(shared, cop_private, thief_private, tmp_path):
    """A complete sub-game: 35 turns, reaching the survival threshold."""
    return await _play(
        shared, cop_private, thief_private, tmp_path,
        shared.movement_and_barriers.survival_threshold, finish=True,
    )


@pytest.fixture
async def partial_logs(shared, cop_private, thief_private, tmp_path):
    """A genuinely unfinished sub-game -- valid chain, no final reveal."""
    return await _play(
        shared, cop_private, thief_private, tmp_path, 3, finish=False
    )


def replay(cop, thief, cfg):
    return replay_logs(cop, thief, cfg)


# ----------------------------------------------------------------------
# The clean case
# ----------------------------------------------------------------------


async def test_valid_two_log_replay(real_logs, cfg):
    cop, thief = real_logs
    verdict = replay(cop, thief, cfg)
    assert verdict.verdict is Verdict.VERIFIED_OK, verdict.describe()
    assert verdict.terminal is not None and verdict.score is not None
    # The peers cannot adjudicate termination themselves -- neither sees the
    # other's position -- so they play to the turn limit and the replay decides
    # where the game actually ended.
    assert 1 <= verdict.turns_verified <= cfg.movement_and_barriers.max_moves
    assert verdict.terminal.turn == verdict.turns_verified


async def test_replay_reconstructs_positions_and_result(real_logs, cfg):
    cop, thief = real_logs
    verdict = replay(cop, thief, cfg)
    # Every frame must place the two agents on distinct, on-board cells.
    for frame in verdict.frames:
        assert frame.cop_position != frame.thief_position
        for cell in (frame.cop_position, frame.thief_position):
            assert 0 <= cell.row < cfg.grid_size
            assert 0 <= cell.col < cfg.grid_size


async def test_viewer_renders_the_board_and_stamp(real_logs, cfg):
    cop, thief = real_logs
    text = render(replay(cop, thief, cfg), cfg.grid_size, max_frames=0)
    assert "VERIFIED OK" in text
    assert "C" in text and "T" in text
    assert "turn 1" in text


# ----------------------------------------------------------------------
# Tampering
# ----------------------------------------------------------------------


async def test_modified_action_is_detected(real_logs, cfg):
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    final = next(r for r in bad if r["event_type"] == "final_reveal")
    final["payload"]["records"][0]["action"] = {
        "v": 1, "kind": "move", "direction": "W",
    }
    verdict = replay(bad, thief, cfg)
    assert verdict.verdict is Verdict.TAMPERED


async def test_modified_nonce_is_detected(real_logs, cfg):
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    final = next(r for r in bad if r["event_type"] == "final_reveal")
    final["payload"]["records"][0]["nonce"] = "c" * 32
    assert replay(bad, thief, cfg).verdict is Verdict.TAMPERED


async def test_deleted_event_is_detected(real_logs, cfg):
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    del bad[3]
    assert replay(bad, thief, cfg).verdict is Verdict.TAMPERED


async def test_reordered_events_are_detected(real_logs, cfg):
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    bad[2], bad[4] = bad[4], bad[2]
    assert replay(bad, thief, cfg).verdict is Verdict.TAMPERED


async def test_duplicated_event_is_detected(real_logs, cfg):
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    bad.insert(4, copy.deepcopy(bad[2]))
    assert replay(bad, thief, cfg).verdict is Verdict.TAMPERED


async def test_mismatched_game_id_is_detected(real_logs, cfg):
    """Caught by the chain, since game_id is inside every record's hash."""
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    for record in bad:
        record["game_id"] = "some-other-game"
    assert replay(bad, thief, cfg).verdict is Verdict.TAMPERED


async def test_mismatched_config_hash_is_detected(real_logs, cfg, tmp_path):
    """Two peers enforcing different physics, each log internally consistent."""
    cop, thief = real_logs
    log = AuditLog(tmp_path / "other.jsonl", game_id="test-game", role="police")
    from police_thief.audit.records import AuditEventType

    start = next(r for r in cop if r["event_type"] == "sub_game_start")
    payload = copy.deepcopy(start["payload"])
    payload["config_sha256"] = "f" * 64
    log.append(AuditEventType.SUB_GAME_START, payload)
    rebuilt = [json.loads(l) for l in log.path.read_text().splitlines()]

    verdict = replay(rebuilt, thief, cfg)
    assert verdict.verdict in (Verdict.TAMPERED, Verdict.INCOMPLETE)
    if verdict.verdict is Verdict.TAMPERED:
        assert "configuration hashes" in verdict.reason


async def test_mismatched_policy_gives_its_own_verdict(real_logs, cfg, tmp_path):
    """Not tampering: two honest peers applying different rules."""
    cop, thief = real_logs
    from police_thief.audit.records import AuditEventType

    log = AuditLog(tmp_path / "p.jsonl", game_id="test-game", role="police")
    start = next(r for r in cop if r["event_type"] == "sub_game_start")
    payload = copy.deepcopy(start["payload"])
    payload["policy"]["capture"] = "swap_counts_as_capture"
    log.append(AuditEventType.SUB_GAME_START, payload)
    rebuilt = [json.loads(l) for l in log.path.read_text().splitlines()]

    verdict = replay(rebuilt, thief, cfg)
    assert verdict.verdict is Verdict.POLICY_MISMATCH
    assert "different resolution policies" in verdict.reason


async def test_illegal_move_is_detected(real_logs, cfg):
    """A move the physics forbids means a peer did not enforce what it agreed."""
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    final = next(r for r in bad if r["event_type"] == "final_reveal")
    # The cop starts at (0,0); N leaves the board.
    final["payload"]["records"][0]["action"] = {
        "v": 1, "kind": "move", "direction": "N",
    }
    verdict = replay(bad, thief, cfg)
    assert verdict.verdict is Verdict.TAMPERED


async def test_thief_placing_a_barrier_is_rejected(real_logs, cfg):
    cop, thief = real_logs
    bad = copy.deepcopy(thief)
    final = next(r for r in bad if r["event_type"] == "final_reveal")
    final["payload"]["records"][0]["action"] = {
        "v": 1, "kind": "place_barrier", "cell": [3, 4],
    }
    assert replay(cop, bad, cfg).verdict is Verdict.TAMPERED


async def test_incorrect_claimed_score_is_contradicted(real_logs, cfg, tmp_path):
    """The verifier recomputes; it never adopts a claim."""
    cop, thief = real_logs
    bad = copy.deepcopy(cop)
    from police_thief.audit.records import AuditEventType

    log = AuditLog(tmp_path / "c.jsonl", game_id="test-game", role="police")
    for record in bad:
        payload = record["payload"]
        if record["event_type"] == "sub_game_end":
            payload = dict(payload)
            payload["claimed"] = {"cop_score": 999, "winner": "police"}
        log.append(
            AuditEventType(record["event_type"]),
            payload,
            turn_number=record["turn_number"],
        )
    rebuilt = [json.loads(l) for l in log.path.read_text().splitlines()]

    verdict = replay(rebuilt, thief, cfg)
    assert verdict.verdict is Verdict.TAMPERED
    assert "claimed" in verdict.reason


async def test_unfinished_game_is_incomplete_not_tampered(partial_logs, cfg):
    """A log that stops early is unfinished, not forged. The distinction
    matters: one is a crash, the other is an accusation."""
    cop, thief = partial_logs
    verdict = replay(cop, thief, cfg)
    assert verdict.verdict is Verdict.INCOMPLETE
    assert "final reveal" in verdict.reason


async def test_deleting_the_final_reveal_breaks_the_chain(real_logs, cfg):
    """Editing a completed log is tampering, however plausible the result."""
    cop, thief = real_logs
    edited = [r for r in cop if r["event_type"] != "final_reveal"]
    assert replay(edited, thief, cfg).verdict is Verdict.TAMPERED


def test_missing_file_is_incomplete(cfg, tmp_path):
    verdict = replay_files(tmp_path / "a.jsonl", tmp_path / "b.jsonl", cfg)
    assert verdict.verdict is Verdict.INCOMPLETE


# ----------------------------------------------------------------------
# Boundary: the live peer must not reach the replay
# ----------------------------------------------------------------------


def test_live_peer_never_imports_the_replay():
    """The viewer may show global truth precisely because it is offline."""
    src = Path("src/police_thief")
    offenders = []
    for path in sorted(src.rglob("*.py")):
        if "replay" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = (
                node.module
                if isinstance(node, ast.ImportFrom) and node.module
                else None
            )
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import) else []
            )
            for name in ([module] if module else []) + names:
                if name and name.startswith("police_thief.replay"):
                    offenders.append(f"{path.name} -> {name}")
    assert not offenders, f"live code imports the replay viewer: {offenders}"
