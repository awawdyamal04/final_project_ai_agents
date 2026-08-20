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
import contextlib
import signal
import sys
import threading
from pathlib import Path

from police_thief.audit.writer import AuditLog
from police_thief.config.exceptions import ConfigError
from police_thief.config.loader import load_private_config, load_shared_config
from police_thief.crypto.exceptions import CommitmentMismatchError
from police_thief.peer.client import PeerClient
from police_thief.peer.clock import SystemClock
from police_thief.peer.events import JsonlEventSink
from police_thief.peer.gui_cli import GUI_DELAY_MAX_SEC, gui_delay_seconds
from police_thief.peer.gui_runtime import _mark_gui_finished, _maybe_gui_pause
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
        "--opponent-url",
        default=None,
        help=(
            "override [network].opponent_url from --private for this run "
            "only -- switch opponents (e.g. to a tunnelled https:// URL) "
            "without editing the TOML file"
        ),
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
        "--gui-delay",
        type=gui_delay_seconds,
        default=0.0,
        metavar="SECONDS",
        help=(
            "pause this many seconds between completed turns, for a human "
            "watching --gui to keep up (default 0 = no pause). Ignored "
            f"without --gui. 0 to {GUI_DELAY_MAX_SEC:g} inclusive; the pause "
            "runs strictly between turns, after commit/reveal/audit for the "
            "finished turn and before the next turn's protocol messages -- "
            "it never extends a deadline, timeout, or the final reveal."
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "echo every operational event to stdout. Off by default: the events "
            "are always written to the JSONL log, and echoing them floods stdout "
            "fast enough that an undrained capture pipe blocks the event loop "
            "(the Q-20 turn-6 freeze). Opt in only when watching a run live."
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

    if args.opponent_url:
        # CLI override only -- the TOML file on disk is never rewritten, so
        # nothing here needs an extra gitignore rule beyond the private file
        # itself (config/<role>/game.toml).
        import dataclasses

        private = dataclasses.replace(
            private,
            network=dataclasses.replace(
                private.network, opponent_url=args.opponent_url
            ),
        )

    role = private.role
    clock = SystemClock()
    events = JsonlEventSink(
        path=Path(args.log_dir) / f"peer_{role.value}_{args.game_id}.jsonl",
        role=role.value,
        game_id=args.game_id,
        echo=args.verbose,
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
                with contextlib.suppress(ValueError):
                    signal.signal(sig, _request_stop)

    gui_task = None
    gui_stop = asyncio.Event()
    if gui_slot is not None:
        from police_thief.gui.live import run_gui
        from police_thief.gui.view_model import snapshot

        # Lets the Tk main thread ask *this* loop to set `stop` -- safely,
        # via call_soon_threadsafe -- when the window is closed or Ctrl+C
        # lands there. Without this, neither trigger ever reached `stop` at
        # all under --gui (see ViewSlot.request_stop).
        gui_slot.bind_stop(asyncio.get_running_loop(), stop)
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
            if exit_code == EXIT_OK and gui_slot is not None:
                # All configured turns, the final reveal, the mutual audit and
                # the audit-chain verification have already succeeded inside
                # _play_turns by the time it returns EXIT_OK. Publish the
                # observer-only completion view now -- before --hold's
                # indefinite wait below -- rather than only at process
                # shutdown (Q-19): a peer sitting in --hold was showing the
                # last ordinary turn_complete snapshot (banner: YOUR TURN) for
                # the entire time a person was actually looking at the
                # window, because final_status was previously set only in
                # this function's `finally` block, which does not run until
                # after Ctrl+C ends the hold.
                _mark_gui_finished(orchestrator, gui_slot, exit_code)

        if args.hold and exit_code == EXIT_OK:
            print("  holding; Ctrl+C to stop")
            await stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if gui_slot is not None:
            # Idempotent with the publish above: covers the failure paths
            # (handshake/turn failure, where the block above never runs) and
            # the case with no --hold (turns finish, no wait, straight to
            # shutdown), and is a harmless no-op re-publish of the same
            # status otherwise.
            _mark_gui_finished(orchestrator, gui_slot, exit_code)
            await asyncio.sleep(0.6)  # let the main thread draw the last frame
            gui_stop.set()
            if gui_task is not None:
                await gui_task
        await orchestrator.shutdown("interrupt" if stop.is_set() else "normal")
        events.emit("transport_diagnostics", **client.diagnostics())
        await client.aclose()
        await server.stop()
        print(f"  shutdown       {orchestrator.machine.state.value}")

    if args.turns:
        _print_match_summary(orchestrator, args, exit_code, private)

    return exit_code


def _print_match_summary(orchestrator, args, exit_code: int, private) -> None:
    """Compact end-of-match status (league readiness Priority 4), plus the
    local JSON report + league index (Priority 5/6). Never fabricates a
    winner or score -- a live peer structurally cannot know it (E-8/E-9);
    that is offline replay's job (D-41), never imported here."""
    from police_thief.reporting.gmail_report import send_report_email
    from police_thief.reporting.match_report import MatchReport, write_report

    status = "MATCH COMPLETE" if exit_code == EXIT_OK else "TECHNICAL LOSS"
    turns_played = len(orchestrator.crypto.completed_turns)
    audit_status = "N/A (no turns completed)"
    if orchestrator.audit is not None and turns_played:
        from police_thief.audit.verifier import verify_chain_file

        audit_status = verify_chain_file(orchestrator.audit.path).describe()

    report = MatchReport(
        game_id=args.game_id,
        role=orchestrator.role.value,
        opponent_url=private.network.opponent_url,
        opponent_team=orchestrator.handshake.opponent_name or "unknown",
        turns_played=turns_played,
        exit_status=status,
        audit_status=audit_status,
    )
    report_path = write_report(report)  # honest "not attempted" pre-send state
    sent, mail_status = send_report_email(
        report,
        report_path,
        recipient=private.email.recipient,
        credentials_path=private.email.credentials_path,
        token_path=private.email.token_path,
    )
    report.gmail_status = mail_status
    write_report(report)  # re-persist with the real, final gmail_status

    print("  " + "=" * 50)
    print(f"  {status}")
    print(f"  game id        {args.game_id}")
    print(f"  opponent       {report.opponent_team} ({private.network.opponent_url})")
    print(f"  role           {orchestrator.role.value}")
    print(f"  turns          {turns_played}")
    print(f"  audit status   {audit_status}")
    print(f"  replay status  {report.replay_status}")
    print(f"  score/result   {report.score}")
    print(f"  gmail          {mail_status}")
    print(f"  report saved   {report_path}")
    print("  " + "=" * 50)
    del sent  # status text already reflects it; kept for clarity at call site


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
            # Strictly after this turn's commit/reveal/audit-log write and
            # before the next turn's protocol messages -- see
            # _maybe_gui_pause's docstring for why this cannot touch a
            # deadline.
            await _maybe_gui_pause(args, orchestrator, turn)
            if orchestrator.capture_claims.pending:
                # CLAIM_PENDING_AUDIT (prd.md Sec 14.13, OUR DESIGN DECISION):
                # a confirmed capture_claim stops new turns, but Final Reveal
                # and mutual audit below still run unconditionally -- the
                # offline replay remains the authoritative terminal call
                # (D-41, augmented not replaced).
                print("  capture_claim  CONFIRMED -- stopping turn loop, audit still runs")
                break
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
        from police_thief.peer.gui_main import _main_with_gui

        return _main_with_gui(args)
    try:
        return asyncio.run(run_peer(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
