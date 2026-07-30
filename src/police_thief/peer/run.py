"""Peer entry point.

    python -m police_thief.peer.run --shared config/game.json \\
                                    --private config/cop.toml.example

Role, listen address and opponent URL all come from the private configuration.
Two peers are two independent invocations of this module; neither supervises the
other, and nothing coordinates them but the protocol itself.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import threading
from pathlib import Path

from police_thief.audit.writer import AuditLog
from police_thief.crypto.exceptions import CommitmentMismatchError
from police_thief.config.exceptions import ConfigError
from police_thief.config.loader import load_private_config, load_shared_config
from police_thief.peer.client import PeerClient
from police_thief.peer.clock import SystemClock
from police_thief.peer.events import JsonlEventSink
from police_thief.peer.orchestrator import PeerOrchestrator
from police_thief.peer.server import PeerServer
from police_thief.peer.states import PeerState

EXIT_OK = 0
EXIT_HANDSHAKE_FAILED = 1
EXIT_CONFIG_ERROR = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m police_thief.peer.run",
        description="Run one peer (cop or thief). Role comes from the private config.",
    )
    parser.add_argument("--shared", default="config/game.json")
    parser.add_argument("--private", required=True)
    parser.add_argument(
        "--game-id",
        default="local-dev",
        help=(
            "match identifier; both peers must be given the same value. "
            "Not in either config file -- it identifies the encounter, which "
            "the two teams agree on out of band."
        ),
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="directory for the operational JSONL log",
    )
    parser.add_argument(
        "--connect-attempts",
        type=int,
        default=30,
        help="how many times to poll for the opponent before giving up",
    )
    parser.add_argument(
        "--hold",
        action="store_true",
        help="stay running after READY (until Ctrl+C) instead of exiting",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=0,
        help="play N cryptographic commit-reveal turns after READY",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help=(
            "open the live window. Shows local truth only; headless without "
            "it, so tests and CI runs are unchanged."
        ),
    )
    parser.add_argument(
        "--screenshot",
        default=None,
        help="save a PNG of the live window to this path before shutdown",
    )
    parser.add_argument(
        "--tamper",
        choices=["action", "nonce"],
        default=None,
        help=(
            "corrupt our own final reveal, to demonstrate that the opponent "
            "detects it (test/demo only)"
        ),
    )
    return parser


async def run_peer(args: argparse.Namespace, gui_slot=None) -> int:
    try:
        shared = load_shared_config(args.shared)
        private = load_private_config(args.private)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    role = private.role
    clock = SystemClock()
    events = JsonlEventSink(
        path=Path(args.log_dir) / f"peer_{role.value}_{args.game_id}.jsonl",
        role=role.value,
        game_id=args.game_id,
        echo=True,
    )

    # Never printed: credential paths, opponent internals, private file body.
    print(f"peer {role.value}")
    print(f"  game_id        {args.game_id}")
    print(f"  listening      http://{private.network.host}:{private.network.port}/mcp")
    print(f"  opponent       {private.network.opponent_url}")
    print(f"  group          {private.game.group_name} ({private.game.group_id})")

    events.emit(
        "process_start",
        listen_port=private.network.port,
        opponent_url=private.network.opponent_url,
    )

    gatekeeper = PeerOrchestrator.build_gatekeeper(shared, clock)
    retry_policy = PeerOrchestrator.build_retry_policy(shared)
    client = PeerClient(
        private.network.opponent_url,
        gatekeeper=gatekeeper,
        retry_policy=retry_policy,
        clock=clock,
        events=events,
    )

    audit = AuditLog(
        path=Path(args.log_dir) / f"audit_{role.value}_{args.game_id}.jsonl",
        game_id=args.game_id,
        role=role.value,
    )

    orchestrator = PeerOrchestrator(
        shared=shared,
        private=private,
        game_id=args.game_id,
        client=client,
        events=events,
        clock=clock,
        audit=audit,
    )

    server = PeerServer(
        peer_name=f"{private.game.group_id}-{role.value}",
        handler=orchestrator.handle_message,
        events=events,
        host=private.network.host,
        port=private.network.port,
    )

    print(f"  config_sha256  {orchestrator.config_hash}")

    stop = asyncio.Event()

    def _request_stop(*_: object) -> None:
        stop.set()

    # Signal handling is only possible on the main thread. Under --gui the peer
    # runs in a worker (Tk owns the main thread), so we skip it there and let
    # the GUI's window-close drive shutdown instead.
    if threading.current_thread() is threading.main_thread():
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_stop)
            except (NotImplementedError, AttributeError, ValueError):
                # Windows ProactorEventLoop does not support
                # add_signal_handler; KeyboardInterrupt still propagates.
                try:
                    signal.signal(sig, _request_stop)
                except ValueError:
                    pass

    gui_task = None
    gui_stop = asyncio.Event()
    if gui_slot is not None:
        from police_thief.gui.live import run_gui
        from police_thief.gui.view_model import snapshot

        gui_task = asyncio.create_task(
            run_gui(gui_slot, lambda: snapshot(orchestrator), gui_stop)
        )
        print("  gui            live window open")

    # Both sessions up before the handshake, so neither is being established
    # for the first time while a turn is in flight.
    await client.open()

    server.start()
    orchestrator.mark_server_ready(server.url)
    orchestrator.watchdog.heartbeat()
    # Give the transport a moment to bind before the opponent polls us.
    await asyncio.sleep(0.5)

    exit_code = EXIT_OK
    try:
        if not await orchestrator.wait_for_peer(attempts=args.connect_attempts):
            print("  handshake      FAILED (opponent unreachable)", file=sys.stderr)
            exit_code = EXIT_HANDSHAKE_FAILED
        elif not await orchestrator.perform_handshake():
            print(
                f"  handshake      FAILED ({orchestrator.failure})",
                file=sys.stderr,
            )
            exit_code = EXIT_HANDSHAKE_FAILED
        else:
            await orchestrator.await_ready()
            if orchestrator.machine.state is PeerState.READY:
                print("  handshake      OK")
                print(f"  state          {orchestrator.machine.state.value}")
                print(f"  opponent       {orchestrator.handshake.opponent_name}")
            else:
                print(
                    f"  handshake      INCOMPLETE "
                    f"({orchestrator.machine.state.value})",
                    file=sys.stderr,
                )
                exit_code = EXIT_HANDSHAKE_FAILED

        if exit_code == EXIT_OK and args.turns:
            exit_code = await _play_turns(orchestrator, args)

        if args.hold and exit_code == EXIT_OK:
            print("  holding; Ctrl+C to stop")
            await stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if gui_slot is not None:
            orchestrator.final_status = (
                "finished - see terminal for audit result"
                if exit_code == EXIT_OK
                else f"failed: {orchestrator.failure or 'see terminal'}"
            )
            from police_thief.gui.view_model import snapshot as _snap

            gui_slot.publish(_snap(orchestrator))
            await asyncio.sleep(0.6)  # let the main thread draw the last frame
            gui_stop.set()
            if gui_task is not None:
                await gui_task
        await orchestrator.shutdown("interrupt" if stop.is_set() else "normal")
        events.emit("transport_diagnostics", **client.diagnostics())
        await client.aclose()
        await server.stop()
        print(f"  shutdown       {orchestrator.machine.state.value}")

    return exit_code


async def _play_turns(orchestrator, args) -> int:
    """Play N cryptographic turns, then exchange final reveals and audit.

    Each peer's own strategy chooses the action from its own belief and the
    opponent's scent. Nothing else is available to it.
    """
    from police_thief.audit.verifier import verify_chain_file
    from police_thief.crypto.exceptions import CryptoError

    try:
        for turn in range(1, args.turns + 1):
            # No action passed: the peer's own strategy chooses, from its own
            # belief and the opponent's scent. Nothing else is available to it.
            # No hint passed: the peer's own verbal layer composes one, and
            # decides for itself whether this turn's is truthful.
            opponent_action = await orchestrator.play_turn(turn)
            crypto_turn = orchestrator.crypto.completed_turns[turn]
            commitment = crypto_turn.local_commitment
            print(
                f"  turn {turn:<3}       commit {commitment[:16]}… "
                f"| opponent revealed {opponent_action}"
            )
    except CryptoError as exc:
        print(f"  turn           FAILED: {exc}", file=sys.stderr)
        return EXIT_HANDSHAKE_FAILED

    if args.tamper:
        _corrupt_final_reveal(orchestrator, args.tamper)
        print(f"  TAMPERING      deliberately corrupted our {args.tamper}")

    # The audit is mutual (E-36): send ours, and stay until we have verified
    # theirs. Leaving early would let one side go unaudited.
    sending = asyncio.create_task(orchestrator.send_final_reveal())
    received = await orchestrator._await_condition(
        lambda: orchestrator.opponent_audit_received
    )
    # A lost acknowledgement is not a failed audit. Whichever peer finishes
    # first tears down its server, so the other's receipt can go missing even
    # though its records arrived and verified. A rejection, by contrast, is a
    # real mismatch and must fail.
    try:
        verified = await sending
        print(f"  final reveal   opponent verified {verified} turn(s)")
    except CommitmentMismatchError as exc:
        print(f"  final reveal   REJECTED: {exc}", file=sys.stderr)
        return EXIT_HANDSHAKE_FAILED
    except Exception:
        print("  final reveal   sent (acknowledgement not received)")

    print(
        f"  mutual audit   "
        f"{'both directions verified' if received else 'INCOMPLETE'}"
    )
    if not received:
        return EXIT_HANDSHAKE_FAILED

    orchestrator.close_sub_game()

    if orchestrator.audit is not None:
        verdict = verify_chain_file(orchestrator.audit.path)
        print(f"  audit chain    {verdict.describe()}")
        if not verdict:
            return EXIT_HANDSHAKE_FAILED

    return EXIT_OK


def _corrupt_final_reveal(orchestrator, what: str) -> None:
    """Demonstration only: falsify our own sealed record after committing."""
    import dataclasses

    from police_thief.domain.actions import Move
    from police_thief.domain.enums import Direction

    trail = orchestrator.crypto.audit_trail
    if not trail:
        return
    if what == "action":
        trail[0] = dataclasses.replace(trail[0], action=Move(Direction.W))
    else:
        trail[0] = dataclasses.replace(trail[0], nonce="c" * 32)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.gui:
        return _main_with_gui(args)
    try:
        return asyncio.run(run_peer(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return EXIT_OK


def _main_with_gui(args: argparse.Namespace) -> int:
    """Tk owns the main thread; the peer's asyncio loop runs in a worker.

    Tk cannot be driven from a worker thread -- it crashes the interpreter on
    Windows -- and cannot be pumped from the asyncio loop, which stalls commit
    exchanges past their deadline and fails turns. Giving it the main thread is
    the arrangement that works, and it is what the architecture notes describe.
    """
    import threading

    from police_thief.config.loader import load_shared_config
    from police_thief.gui.capture import save_window_png
    from police_thief.gui.live import PeerWindow, ViewSlot, drive_on_main_thread

    try:
        shared = load_shared_config(args.shared)
        private = load_private_config(args.private)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    try:
        window = PeerWindow(
            f"police-thief - {private.role.value}", shared.grid_size
        )
    except Exception as exc:
        print(f"  gui            unavailable ({type(exc).__name__}); headless")
        return asyncio.run(run_peer(args))

    slot = ViewSlot()
    result: dict[str, int] = {}

    def worker() -> None:
        try:
            result["code"] = asyncio.run(run_peer(args, gui_slot=slot))
        except KeyboardInterrupt:
            result["code"] = EXIT_OK
        except Exception as exc:  # pragma: no cover - defensive
            print(f"peer failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            result["code"] = EXIT_HANDSHAKE_FAILED
        finally:
            slot.stop()

    thread = threading.Thread(target=worker, name="peer", daemon=True)
    thread.start()
    drive_on_main_thread(window, slot)
    thread.join(timeout=60)

    if args.screenshot:
        saved = save_window_png(window, args.screenshot)
        print(f"  screenshot     {saved or 'unavailable'}")
    window.close()
    return result.get("code", EXIT_HANDSHAKE_FAILED)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
