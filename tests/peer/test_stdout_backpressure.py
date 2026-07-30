"""Regression guard for the Q-20 stdout-backpressure freeze.

Two REAL peer subprocesses play over loopback HTTP with their stdout captured
through UNDRAINED pipes -- the exact condition that froze the event loop at
turn 6. Under the old default (``JsonlEventSink(echo=True)`` plus uvicorn's
per-request INFO lines) the pipe buffer filled after a few turns and the next
synchronous ``print`` blocked the loop; the FastMCP server then stopped
servicing while the process stayed alive (~40s loop lag in the diagnostic).

With the fix -- echo off by default and uvicorn ``log_level="warning"`` -- the
undrained pipes stay tiny, so the loop never blocks and both peers play well past
turn 6. The test deliberately never reads stdout during the run (``wait`` does not
drain), so a regression would re-block a peer and this test would fail.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from tests.conftest import COP_EXAMPLE_PATH, SHARED_CONFIG_PATH, THIEF_EXAMPLE_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
TURNS = 12
TIMEOUT = 55
MAX_STDOUT_BYTES = 16384
GAME_ID = "q20-stdout-regression"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _write_private(src: Path, dst: Path, own_port: int, opp_port: int) -> None:
    """Copy a role's example TOML, retargeting only its port and opponent URL."""
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"port\s*=\s*\d+", f"port = {own_port}", text, count=1)
    text = re.sub(
        r"http://127\.0\.0\.1:\d+/mcp", f"http://127.0.0.1:{opp_port}/mcp", text, count=1
    )
    dst.write_text(text, encoding="utf-8")


def _cmd(private: Path, log_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "police_thief.peer.run",
        "--shared", str(SHARED_CONFIG_PATH), "--private", str(private),
        "--game-id", GAME_ID, "--turns", str(TURNS), "--log-dir", str(log_dir),
    ]


def _read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _max_turn(events: list[dict]) -> int:
    turns = [e["turn"] for e in events if e.get("event") == "turn_complete" and "turn" in e]
    return max(turns) if turns else 0


def test_q20_undrained_stdout_pipe_does_not_freeze_two_peers(tmp_path):
    port_a, port_b = _free_port(), _free_port()
    cop_priv, thief_priv = tmp_path / "cop.toml", tmp_path / "thief.toml"
    _write_private(COP_EXAMPLE_PATH, cop_priv, port_a, port_b)
    _write_private(THIEF_EXAMPLE_PATH, thief_priv, port_b, port_a)
    log_dir = tmp_path / "logs"

    # PYTHONUTF8 so the '…' the turn summary prints cannot crash a child on a
    # non-UTF-8 Windows console; it is unrelated to the freeze under test.
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def popen(private: Path) -> subprocess.Popen:
        return subprocess.Popen(
            _cmd(private, log_dir), cwd=REPO_ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env,
        )

    cop, thief = popen(cop_priv), popen(thief_priv)
    outs: dict[str, str] = {}
    try:
        # UNDRAINED on purpose: wait() does not read the pipes while the game
        # runs. If stdout flooded, a peer would block on write and never exit.
        deadline = time.monotonic() + TIMEOUT
        cop.wait(timeout=TIMEOUT)
        thief.wait(timeout=max(1.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        pass
    finally:
        for name, proc in (("cop", cop), ("thief", thief)):
            if proc.poll() is None:
                proc.kill()
            try:
                outs[name] = proc.communicate(timeout=10)[0] or ""
            except Exception:
                outs[name] = ""

    # 1. Both finished cleanly. In run.py, exit 0 is only reached after the final
    #    reveal, the mutual audit ("both directions verified") and the audit-chain
    #    "Verified OK"; a stall or rejection returns non-zero.
    assert cop.returncode == 0, f"cop exit {cop.returncode}\n{outs['cop'][-1500:]}"
    assert thief.returncode == 0, f"thief exit {thief.returncode}\n{outs['thief'][-1500:]}"

    # 2. The undrained pipes stayed small -- proof the flood is gone and the loop
    #    was never at risk of blocking on a full pipe.
    assert len(outs["cop"]) < MAX_STDOUT_BYTES, len(outs["cop"])
    assert len(outs["thief"]) < MAX_STDOUT_BYTES, len(outs["thief"])

    # 3. Corroborate via the logs (not exit codes alone): the peers handshook,
    #    exchanged commits/reveals both ways, and progressed past the turn-6 wall.
    cop_ev = _read_events(log_dir / f"peer_police_{GAME_ID}.jsonl")
    thief_ev = _read_events(log_dir / f"peer_thief_{GAME_ID}.jsonl")
    assert any(e.get("event") == "ready" for e in cop_ev)
    assert any(e.get("event") == "opponent_commit" for e in cop_ev)
    assert any(e.get("event") == "opponent_reveal" for e in thief_ev)
    assert _max_turn(cop_ev) >= 10, _max_turn(cop_ev)
    assert _max_turn(thief_ev) >= 10, _max_turn(thief_ev)
    assert not any(e.get("event") == "send_unacknowledged" for e in cop_ev + thief_ev)

    # 4. Operational + cryptographic audit JSONL logging is still active
    #    (events were quieted on stdout, never removed from the files).
    assert (log_dir / f"audit_police_{GAME_ID}.jsonl").stat().st_size > 0
    assert (log_dir / f"audit_thief_{GAME_ID}.jsonl").stat().st_size > 0
