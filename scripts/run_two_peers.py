"""Launch two real peer processes and report the result.

    python scripts/run_two_peers.py

Test and demonstration infrastructure. It **launches** two processes and then
gets out of the way: it sends them no messages, holds no game state, and
adjudicates nothing. Everything the two peers agree on, they agree on by talking
to each other.

Each peer is independently executable -- the two commands this script runs can
be typed by hand in two terminals, which is how a real match is played, with the
two processes on different machines.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def peer_command(private: str, game_id: str, shared: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "police_thief.peer.run",
        "--shared",
        shared,
        "--private",
        private,
        "--game-id",
        game_id,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared", default="config/game.json")
    parser.add_argument("--cop", default="config/cop.toml.example")
    parser.add_argument("--thief", default="config/thief.toml.example")
    parser.add_argument("--game-id", default="local-dev")
    parser.add_argument(
        "--stagger",
        type=float,
        default=0.0,
        help="seconds to delay the thief, to demonstrate a late start",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    cop_cmd = peer_command(args.cop, args.game_id, args.shared)
    thief_cmd = peer_command(args.thief, args.game_id, args.shared)

    print("launching two independent peer processes")
    print(f"  cop   : {' '.join(cop_cmd[-6:])}")
    print(f"  thief : {' '.join(thief_cmd[-6:])}")
    if args.stagger:
        print(f"  thief delayed by {args.stagger}s")
    print()

    cop = subprocess.Popen(
        cop_cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    if args.stagger:
        time.sleep(args.stagger)
    thief = subprocess.Popen(
        thief_cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )

    print(f"  cop   pid {cop.pid}")
    print(f"  thief pid {thief.pid}")
    assert cop.pid != thief.pid, "two distinct OS processes"
    print()

    try:
        cop_out = cop.communicate(timeout=args.timeout)[0]
        thief_out = thief.communicate(timeout=args.timeout)[0]
    except subprocess.TimeoutExpired:
        cop.kill()
        thief.kill()
        print("TIMEOUT: peers did not finish", file=sys.stderr)
        return 1

    for name, out in (("COP", cop_out), ("THIEF", thief_out)):
        print(f"----- {name} (exit {cop.returncode if name == 'COP' else thief.returncode}) -----")
        print(out.rstrip())
        print()

    ok = cop.returncode == 0 and thief.returncode == 0
    print("RESULT:", "both peers reached READY" if ok else "handshake failed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
