"""``--gui``'s process entry point: Tk on the main thread, the peer's asyncio
runtime in a worker thread.

Split out of ``peer/run.py`` (Q-19, D-44). Imports ``run_peer`` and the exit
codes from ``peer.run`` *locally*, inside the function body, rather than at
module level -- ``run.py`` imports ``_main_with_gui`` from here at its own
module level, so a top-level import back would be circular. This mirrors the
local-import style ``run.py`` itself already used for GUI dependencies before
this split.
"""

from __future__ import annotations

import asyncio
import sys
import threading

from police_thief.config.exceptions import ConfigError
from police_thief.config.loader import load_private_config, load_shared_config


def _main_with_gui(args) -> int:
    """Tk owns the main thread; the peer's asyncio loop runs in a worker.

    Tk cannot be driven from a worker thread -- it crashes the interpreter on
    Windows -- and cannot be pumped from the asyncio loop, which stalls commit
    exchanges past their deadline and fails turns. Giving it the main thread is
    the arrangement that works, and it is what the architecture notes describe.

    Two responsibilities beyond driving the window live here: screenshot
    evidence (delegated to ``drive_on_main_thread``, which fires it on this
    thread the moment GAME COMPLETE is actually drawn -- see
    ``gui/capture.py``'s ``should_capture``) and a clean shutdown on Ctrl+C
    or the window's close button, both of which now ask the worker's own
    loop to unwind via ``ViewSlot.request_stop`` instead of leaving it
    abandoned mid-``--hold`` when the 60s join below times out.
    """
    from police_thief.gui.live import PeerWindow
    from police_thief.gui.main_loop import drive_on_main_thread
    from police_thief.gui.view_slot import ViewSlot
    from police_thief.peer.run import (
        EXIT_CONFIG_ERROR,
        EXIT_HANDSHAKE_FAILED,
        EXIT_OK,
        run_peer,
    )

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

    outcome = None
    try:
        outcome = drive_on_main_thread(window, slot, screenshot_path=args.screenshot)
    except KeyboardInterrupt:
        # Belt and braces: drive_on_main_thread already catches this around
        # mainloop() itself. This covers a signal landing just outside that
        # window (e.g. while the first `after` callback is being scheduled),
        # so nothing here can propagate out of main() uncaught.
        slot.request_stop()

    try:
        thread.join(timeout=60)
    except KeyboardInterrupt:
        slot.request_stop()
        thread.join(timeout=60)

    if args.screenshot:
        if outcome is None:
            print("  screenshot     unavailable (match never reached GAME COMPLETE)")
        elif outcome.path is None:
            print(f"  screenshot     FAILED: {outcome.detail}")
        elif outcome.degraded:
            print(f"  screenshot     degraded: {outcome.detail}")
        else:
            print(f"  screenshot     {outcome.path}")

    window.close()
    return result.get("code", EXIT_HANDSHAKE_FAILED)
