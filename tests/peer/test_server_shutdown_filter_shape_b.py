"""``_QuietExpectedLifespanCancellation``, Shape B: the shape that actually
fires in practice -- the message IS the rendered traceback, ``exc_info`` is
``None``. This is the real regression coverage for the Windows failure;
these would all have failed against the first (Shape-A-only) filter.

Split out of ``test_server_shutdown.py`` (150-line compliance pass, D-44).
See ``test_server_shutdown_filter.py`` for Shape A, and
``police_thief.peer.lifespan_filter`` for the full root-cause reasoning.
"""

from __future__ import annotations

import asyncio
import logging
import traceback

from police_thief.peer.events import MemoryEventSink
from police_thief.peer.lifespan_filter import (
    _LIFESPAN_LOGGER_NAME,
    _QuietExpectedLifespanCancellation,
)
from police_thief.peer.server import PeerServer


def _formatted_traceback_record(
    *, logger_name: str = _LIFESPAN_LOGGER_NAME, exc: BaseException
) -> logging.LogRecord:
    """Build a Shape-B-style record: the message *is* a pre-rendered
    traceback (traceback.format_exc()), exc_info left unset -- exactly what
    LifespanOn.send()'s "lifespan.shutdown.failed" branch actually logs."""
    try:
        raise exc
    except type(exc):
        text = traceback.format_exc()
    return logging.LogRecord(logger_name, logging.ERROR, __file__, 1, text, (), None)


async def _handler(_envelope):
    return {"ok": True, "error": None}


def _make_lifespan_style_cancelled_error() -> BaseException:
    """A CancelledError raised through frames literally named `lifespan`
    and `receive`, so the rendered traceback contains "in lifespan" and "in
    receive" exactly as the real one does -- without needing a real server."""

    async def receive():
        raise asyncio.CancelledError()

    async def lifespan():
        await receive()

    coro = lifespan()
    try:
        coro.send(None)
    except StopIteration:
        pass
    except BaseException as exc:  # noqa: BLE001 - capturing for the traceback shape
        return exc
    raise AssertionError("lifespan() should have raised")


def test_filter_drops_shape_b_the_real_benign_lifespan_cancellation():
    """A pre-formatted traceback whose last line names CancelledError and
    whose frames are Starlette's lifespan() awaiting uvicorn's receive() --
    exactly what a real shutdown produces. This is the record the first
    filter missed."""
    exc = _make_lifespan_style_cancelled_error()
    f = _QuietExpectedLifespanCancellation()
    record = _formatted_traceback_record(exc=exc)
    assert f.filter(record) is False


def test_filter_keeps_shape_b_a_genuine_different_exception():
    """A real bug during shutdown, reported the same way (pre-formatted
    traceback, no exc_info) -- must still be visible."""
    f = _QuietExpectedLifespanCancellation()
    record = _formatted_traceback_record(exc=RuntimeError("startup actually broke"))
    assert f.filter(record) is True


def test_filter_keeps_shape_b_an_unrelated_cancelled_error():
    """Same final line (CancelledError), but NOT through the lifespan/
    receive call chain -- a coincidence, not the benign case, and must not
    be dropped just because the exception type matches."""

    async def somewhere_else():
        raise asyncio.CancelledError()

    coro = somewhere_else()
    try:
        coro.send(None)
    except StopIteration:
        pass
    except BaseException as exc:
        f = _QuietExpectedLifespanCancellation()
        record = _formatted_traceback_record(exc=exc)
        assert f.filter(record) is True
        return
    raise AssertionError("somewhere_else() should have raised")


def test_filter_keeps_shape_b_records_from_other_loggers():
    f = _QuietExpectedLifespanCancellation()
    exc = _make_lifespan_style_cancelled_error()
    record = _formatted_traceback_record(logger_name="uvicorn.access", exc=exc)
    assert f.filter(record) is True


def test_filter_is_installed_exactly_once_across_multiple_servers():
    """PeerServer.__post_init__ installs the filter; constructing several
    servers in one process (as tests routinely do) must not stack
    duplicates on the shared uvicorn.error logger."""
    logger = logging.getLogger(_LIFESPAN_LOGGER_NAME)

    PeerServer(peer_name="a", handler=_handler, events=MemoryEventSink(), port=0)
    PeerServer(peer_name="b", handler=_handler, events=MemoryEventSink(), port=0)
    PeerServer(peer_name="c", handler=_handler, events=MemoryEventSink(), port=0)

    after = [f for f in logger.filters if isinstance(f, _QuietExpectedLifespanCancellation)]
    assert len(after) == 1, "the same filter instance must never be added twice"
