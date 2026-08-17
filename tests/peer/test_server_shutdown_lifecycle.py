"""Clean, quiet shutdown of the peer's FastMCP/uvicorn server: the real
end-to-end regression test and the ``stop()`` contract.

Split out of ``test_server_shutdown.py`` (150-line compliance pass, D-44).
See ``test_server_shutdown_filter.py`` / ``test_server_shutdown_filter_shape_b.py``
for the fast synthetic-record filter unit tests,
``test_server_shutdown_logging.py`` for the genuine-error-is-never-swallowed
proofs, ``test_server_shutdown_normal_lifecycle.py`` for the ordinary
start/stop path, and ``police_thief.peer.lifespan_filter`` for the full
root-cause reasoning this module's docstring used to carry.

No real network client is used anywhere in this file, so none of it depends
on this sandbox's flaky outbound-HTTP path (the pre-existing
test_http_stress.py / test_stdout_backpressure.py / two test_channels.py
failures are unrelated).
"""

from __future__ import annotations

import asyncio

from police_thief.peer.events import MemoryEventSink
from police_thief.peer.server import PeerServer


async def _handler(_envelope):
    return {"ok": True, "error": None}


# ----------------------------------------------------------------------
# THE regression test: recreates the actual runtime logging path end to
# end. A real PeerServer, started for real, stopped for real via the
# unmodified production stop(), with uvicorn's own logging configuration
# having genuinely run -- then the orphaned lifespan task is swept up
# exactly as asyncio.run()'s own end-of-program cleanup would at real
# process exit. This is the test that would have caught the Windows
# failure; it fails against a working tree carrying only the first
# (Shape-A-only) filter.
# ----------------------------------------------------------------------


async def test_real_shutdown_path_does_not_log_the_benign_cancellation(monkeypatch, capfd):
    """Captures at the file-descriptor level (what actually lands in a
    terminal), not via caplog: uvicorn installs its own real logging
    handler on "uvicorn.error" once Config.configure_logging() runs (a
    plain StreamHandler(sys.stderr) via its default LOGGING_CONFIG), so the
    faithful reproduction of "does the user see a traceback" is stderr
    content, not pytest's log-capture machinery -- confirmed necessary
    empirically: with the old (Shape-A-only) filter, this test's own
    process visibly printed the ERROR traceback to stderr while caplog's
    records list stayed empty for it, meaning caplog alone would have
    reported this test as passing even against the known-broken filter.
    """
    import uvicorn.server as uvicorn_server_mod

    main_loop_entered = asyncio.Event()
    orig_main_loop = uvicorn_server_mod.Server.main_loop

    async def traced_main_loop(self):
        main_loop_entered.set()
        return await orig_main_loop(self)

    monkeypatch.setattr(uvicorn_server_mod.Server, "main_loop", traced_main_loop)

    server = PeerServer(
        peer_name="real-shutdown-path",
        handler=_handler,
        events=MemoryEventSink(),
        host="127.0.0.1",
        port=0,
    )

    server.start()
    # Wait until uvicorn's Server is genuinely inside its own serving loop
    # -- i.e. past Config.load()/configure_logging() and Server.startup(),
    # which is also what spawns uvicorn's internal lifespan task -- rather
    # than an arbitrary sleep. This is the state a real, minutes-long match
    # is in for virtually its entire lifetime.
    await asyncio.wait_for(main_loop_entered.wait(), timeout=10)
    await asyncio.sleep(0.1)

    capfd.readouterr()  # discard startup noise ("Started server process", etc.)

    await server.stop()  # the unmodified production shutdown path

    # server.stop() only cancels+awaits the outer serve_forever() task; the
    # orphaned internal lifespan task is left pending, exactly as in
    # production. At real process exit, asyncio.run() sweeps this up
    # itself; inside a single test there is no such sweep, so this
    # reproduces it explicitly -- the same operation, at the same point in
    # the sequence.
    current = asyncio.current_task()
    leftover = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    for t in leftover:
        t.cancel()
    if leftover:
        await asyncio.gather(*leftover, return_exceptions=True)

    out, err = capfd.readouterr()
    combined = out + err
    assert "CancelledError" not in combined, (
        "a CancelledError traceback reached stderr after a requested "
        f"shutdown; captured output:\n{combined}"
    )


# ----------------------------------------------------------------------
# PeerServer.stop() itself still does exactly what it did before (cancel +
# suppress our own await), nothing more. Trigger points (X-close / Ctrl+C
# -> request_stop) are unchanged by this fix -- covered in
# tests/gui/test_gui_shutdown.py.
# ----------------------------------------------------------------------


async def test_stop_still_cancels_and_suppresses_its_own_await():
    async def never_finishes():
        await asyncio.Event().wait()

    server = PeerServer(peer_name="contract", handler=_handler, events=MemoryEventSink(), port=0)
    server._task = asyncio.create_task(never_finishes())

    await server.stop()  # must not raise

    assert server._task is None
