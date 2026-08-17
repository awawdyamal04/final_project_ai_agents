"""``_QuietExpectedLifespanCancellation``, Shape A: the previous filter's only
case (fixed prefix + ``exc_info``). Kept because ``LifespanOn.main()`` can
still take this path for a *different* kind of lifespan failure; not the one
this bug actually hit, but still a real, valid case to keep quiet.

Split out of ``test_server_shutdown.py`` (150-line compliance pass, D-44).
See ``test_server_shutdown_filter_shape_b.py`` for the shape that actually
fires in practice, and ``police_thief.peer.lifespan_filter`` for the full
root-cause reasoning.
"""

from __future__ import annotations

import asyncio
import logging

from police_thief.peer.lifespan_filter import (
    _LIFESPAN_LOGGER_NAME,
    _QuietExpectedLifespanCancellation,
)


def _record(
    *,
    logger_name: str = _LIFESPAN_LOGGER_NAME,
    message: str = "Exception in 'lifespan' protocol\n",
    exc: BaseException | None = None,
) -> logging.LogRecord:
    """Build a Shape-A-style record: fixed message text, exception via exc_info."""
    exc_info = (type(exc), exc, exc.__traceback__) if exc is not None else None
    return logging.LogRecord(logger_name, logging.ERROR, __file__, 1, message, (), exc_info)


def test_filter_drops_shape_a_expected_cancellation_record():
    f = _QuietExpectedLifespanCancellation()
    assert f.filter(_record(exc=asyncio.CancelledError())) is False


def test_filter_keeps_shape_a_with_a_genuine_exception_type():
    f = _QuietExpectedLifespanCancellation()
    assert f.filter(_record(exc=ValueError("something actually broke"))) is True


def test_filter_keeps_shape_a_cancelled_error_with_an_unrelated_message():
    f = _QuietExpectedLifespanCancellation()
    record = _record(message="some unrelated uvicorn error", exc=asyncio.CancelledError())
    assert f.filter(record) is True


def test_filter_keeps_empty_messages():
    f = _QuietExpectedLifespanCancellation()
    record = logging.LogRecord(_LIFESPAN_LOGGER_NAME, logging.ERROR, __file__, 1, "", (), None)
    assert f.filter(record) is True
