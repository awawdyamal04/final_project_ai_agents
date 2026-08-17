"""Normal server start/stop lifecycle remains successful, promptly, and does
not leave anything hanging.

Split out of ``test_server_shutdown.py`` (150-line compliance pass, D-44);
see ``test_server_shutdown_lifecycle.py`` for the real shutdown-traceback
regression test and the ``stop()`` contract.
"""

from __future__ import annotations

import asyncio
import time

from police_thief.peer.events import MemoryEventSink
from police_thief.peer.server import PeerServer


async def _handler(_envelope):
    return {"ok": True, "error": None}


async def test_server_start_then_stop_completes_promptly_without_raising():
    server = PeerServer(
        peer_name="shutdown-lifecycle",
        handler=_handler,
        events=MemoryEventSink(),
        host="127.0.0.1",
        port=0,
    )
    task = server.start()
    await asyncio.sleep(0.2)

    started = time.monotonic()
    await asyncio.wait_for(server.stop(), timeout=5)
    elapsed = time.monotonic() - started

    assert elapsed < 5, "stop() must not hang waiting for graceful shutdown"
    assert task.cancelled() or task.done()
    assert server._task is None


async def test_stop_is_idempotent_and_a_second_call_is_a_prompt_no_op():
    server = PeerServer(
        peer_name="shutdown-idempotent",
        handler=_handler,
        events=MemoryEventSink(),
        host="127.0.0.1",
        port=0,
    )
    server.start()
    await asyncio.sleep(0.2)

    await asyncio.wait_for(server.stop(), timeout=5)
    await asyncio.wait_for(server.stop(), timeout=1)  # already stopped: must return fast
