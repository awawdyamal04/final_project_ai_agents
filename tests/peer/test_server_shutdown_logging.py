"""Genuine errors through the REAL "uvicorn.error" logger (not a fabricated
``LogRecord``) must still surface -- proven against the same logger identity
the lifespan-cancellation filter is actually installed on.

Split out of ``test_server_shutdown.py`` (150-line compliance pass, D-44).
"""

from __future__ import annotations

import logging
import traceback

from police_thief.peer.events import MemoryEventSink
from police_thief.peer.lifespan_filter import _LIFESPAN_LOGGER_NAME
from police_thief.peer.server import PeerServer


async def _handler(_envelope):
    return {"ok": True, "error": None}


def test_real_logger_shape_a_genuine_exception_is_not_swallowed(caplog):
    PeerServer(peer_name="genuine-a", handler=_handler, events=MemoryEventSink(), port=0)
    logger = logging.getLogger(_LIFESPAN_LOGGER_NAME)
    caplog.set_level(logging.DEBUG)

    try:
        raise ValueError("a real bug, not a cancellation")
    except ValueError as exc:
        logger.error("Exception in 'lifespan' protocol\n", exc_info=exc)

    matches = [
        r for r in caplog.records
        if r.name == _LIFESPAN_LOGGER_NAME and "ValueError" in str(r.exc_info)
    ]
    assert matches, "a genuine ValueError must still be logged"


def test_real_logger_shape_b_genuine_exception_is_not_swallowed(caplog):
    PeerServer(peer_name="genuine-b", handler=_handler, events=MemoryEventSink(), port=0)
    logger = logging.getLogger(_LIFESPAN_LOGGER_NAME)
    caplog.set_level(logging.DEBUG)

    try:
        raise RuntimeError("startup actually broke")
    except RuntimeError:
        logger.error(traceback.format_exc())

    matches = [
        r for r in caplog.records
        if r.name == _LIFESPAN_LOGGER_NAME and "startup actually broke" in r.getMessage()
    ]
    assert matches, "a genuine RuntimeError, reported the same way, must still be logged"


def test_real_logger_unrelated_uvicorn_error_is_not_swallowed(caplog):
    PeerServer(peer_name="genuine-unrelated", handler=_handler, events=MemoryEventSink(), port=0)
    logger = logging.getLogger(_LIFESPAN_LOGGER_NAME)
    caplog.set_level(logging.DEBUG)

    logger.error("Application startup failed. Exiting.")

    matches = [
        r for r in caplog.records
        if r.name == _LIFESPAN_LOGGER_NAME and "Application startup failed" in r.getMessage()
    ]
    assert matches, "unrelated uvicorn.error messages must never be touched"
