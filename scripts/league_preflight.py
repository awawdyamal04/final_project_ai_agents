#!/usr/bin/env python
"""League preflight (league readiness Priority 3): check an opponent before
starting a counting match, using only what the protocol itself already
provides -- reachability, the HELLO/capability exchange, and the signed
config hash. These are exactly the checks ``PeerOrchestrator.wait_for_peer``/
``perform_handshake`` make at the start of every real match; this script
just runs them once, standalone (no server of our own needs to be up, since
every step here is client-initiated), and reports the result clearly instead
of failing deep inside a counting match.

    python scripts/league_preflight.py --private config/police/game.toml \\
        [--opponent-url https://theirs.ngrok-free.app/mcp] [--attempts 5]

Exit 0 on a clean handshake, 1 otherwise, with an actionable one-line reason.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from police_thief.config.exceptions import ConfigError  # noqa: E402
from police_thief.config.loader import load_private_config, load_shared_config  # noqa: E402
from police_thief.peer.client import PeerClient  # noqa: E402
from police_thief.peer.clock import SystemClock  # noqa: E402
from police_thief.peer.events import NullEventSink  # noqa: E402
from police_thief.peer.orchestrator import PeerOrchestrator  # noqa: E402

_REASONS = {
    "hello_rejected": "endpoint reachable but rejected our HELLO -- not a compatible peer",
    "missing_capability": "the opponent does not support a mandatory protocol capability",
    "config_exchange_failed": "the opponent rejected our CONFIG_HASH message",
    "config_mismatch": (
        "config/game.json differs between teams -- confirm you both have "
        "the identical signed shared config file"
    ),
    "unexpected_reply": "unexpected reply type -- likely a protocol/version mismatch",
    "ready_rejected": "the opponent rejected our READY message",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared", default="config/game.json")
    parser.add_argument("--private", required=True)
    parser.add_argument(
        "--opponent-url", default=None, help="override [network].opponent_url"
    )
    parser.add_argument("--attempts", type=int, default=5, help="reachability polls")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between")
    return parser


async def preflight(args: argparse.Namespace) -> int:
    try:
        shared = load_shared_config(args.shared)
        private = load_private_config(args.private)
    except ConfigError as exc:
        print(f"FAIL  config error: {exc}")
        return 1

    if args.opponent_url:
        private = dataclasses.replace(
            private,
            network=dataclasses.replace(
                private.network, opponent_url=args.opponent_url
            ),
        )

    print(f"preflight      {private.role.value} -> {private.network.opponent_url}")
    clock = SystemClock()
    events = NullEventSink()
    client = PeerClient(
        private.network.opponent_url,
        gatekeeper=PeerOrchestrator.build_gatekeeper(shared, clock),
        retry_policy=PeerOrchestrator.build_retry_policy(shared),
        clock=clock,
        events=events,
    )
    orchestrator = PeerOrchestrator(
        shared=shared, private=private, game_id="preflight",
        client=client, events=events, clock=clock,
    )

    try:
        await asyncio.wait_for(client.open(), timeout=args.attempts * args.interval + 5)
    except Exception as exc:
        print(
            f"FAIL  could not open a connection to the opponent: {exc!r} -- "
            f"check the URL is exactly right (scheme, host, port, /mcp path) "
            f"and that any tunnel is still up"
        )
        return 1

    try:
        if not await orchestrator.wait_for_peer(
            attempts=args.attempts, interval=args.interval
        ):
            print(
                "FAIL  opponent unreachable -- check the URL, the tunnel, "
                "and that their peer process is actually running"
            )
            return 1
        print("OK    endpoint reachable")

        if not await orchestrator.perform_handshake():
            print(
                f"FAIL  {orchestrator.failure}: "
                f"{_REASONS.get(orchestrator.failure or '', 'see handshake_failed event')}"
            )
            return 1

        print("OK    HELLO / capabilities accepted")
        print(
            f"OK    opponent      {orchestrator.handshake.opponent_name} "
            f"(software {orchestrator.handshake.opponent_software_version})"
        )
        print("OK    config_sha256 matches -- same physics")
        print("OK    READY accepted")
        print("PASS  preflight complete -- safe to start a counting match")
        return 0
    finally:
        await client.aclose()


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(preflight(args))


if __name__ == "__main__":
    raise SystemExit(main())
