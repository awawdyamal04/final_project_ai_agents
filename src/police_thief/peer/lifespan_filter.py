"""Mutes exactly one uvicorn-internal log record on shutdown. Nothing else.

Split out of ``peer/server.py`` (Q-19, D-44) -- self-contained logging-filter
logic with no dependency on :class:`PeerServer` itself; ``server.py`` only
calls :func:`_install_lifespan_cancellation_filter` once, from
``PeerServer.__post_init__``.

Root cause (see ``PeerServer.stop``): ``mcp.run_async(...)`` builds its own
``uvicorn.Server`` internally and never exposes it, so the only way to stop
the peer's server task from here is to cancel the ``asyncio.Task`` wrapping
the whole call -- not uvicorn's own graceful ``should_exit`` flag, which is
the mechanism uvicorn is actually built around but which requires a
``Server`` reference this code does not have. Cancelling mid-``main_loop()``
skips uvicorn's own ``Server.shutdown()``, so uvicorn's internal lifespan
task (spawned by its own ``LifespanOn.startup()``, likewise never exposed to
calling code) is left parked forever on an internal queue, waiting for a
"lifespan.shutdown" message that ``Server.shutdown()`` would have sent and
now never will. It sits pending -- not an error yet, just orphaned -- until
``asyncio.run()``'s own end-of-program task sweep (``_cancel_all_tasks``)
cancels it, which happens *after* ``run_peer`` has already returned and
printed "shutdown finished".
"""

from __future__ import annotations

import asyncio
import logging

_LIFESPAN_LOGGER_NAME = "uvicorn.error"

# The previous version of this filter matched on the wrong record shape --
# see the class docstring below. Two possible shapes are matched now:
#
# Shape A: LifespanOn.main()'s own `except BaseException as exc: ...
# self.logger.error(msg, exc_info=exc)`, msg fixed, exception passed via
# exc_info. Kept for defence in depth even though the empirical trace below
# shows this is not the path actually taken for this bug.
_LIFESPAN_ERROR_PREFIX = "Exception in 'lifespan' protocol"

# Shape B: the path actually taken, confirmed by instrumenting a real
# PeerServer start -> stop cycle against the installed fastmcp/uvicorn/
# starlette and inspecting the literal LogRecord. Starlette's own
# `Router.lifespan()` catches the cancellation *itself* (one level inside
# uvicorn's LifespanOn.main(), not at it), formats it with
# `traceback.format_exc()`, and reports it through the ASGI protocol as a
# `{"type": "lifespan.shutdown.failed", "message": <that formatted text>}`
# message. `LifespanOn.send()` handles that message type with
# `self.logger.error(message["message"])` -- a bare string, *no* `exc_info`
# at all. The record's message is therefore the full rendered traceback
# text, not a short fixed string, and `record.exc_info` is `None`. Matching
# must therefore inspect the message text itself: the final line names
# CancelledError, and two of the frames above it are Starlette's `lifespan`
# and uvicorn's `receive` -- both *function* names, stable across platforms
# and install paths (unlike the `File "..."` path components, which are
# not).
_CANCELLED_ERROR_LAST_LINE_PREFIXES = (
    "asyncio.exceptions.CancelledError",
    "asyncio.CancelledError",
    "concurrent.futures.CancelledError",
)
_LIFESPAN_CANCELLATION_FRAME_SIGNATURES = ("in lifespan", "in receive")


class _QuietExpectedLifespanCancellation(logging.Filter):
    """Mutes exactly one uvicorn-internal log record. Nothing else.

    A first version of this filter matched only Shape A above (a fixed
    message prefix plus ``exc_info``) and was proven, on real Windows runs,
    not to catch the actual record. Instrumenting a real
    ``PeerServer.start()`` -> ``stop()`` cycle against the exact installed
    package versions (not the filter in isolation) showed why: the record
    that is actually emitted is Shape B -- see the module-level comment
    above ``_CANCELLED_ERROR_LAST_LINE_PREFIXES``. This filter now matches
    both shapes; Shape B is the one that fires in practice.

    Either way, this filter tells the benign case apart from a real one
    without ever inspecting exception *type* alone in isolation: Shape A
    requires the exception to be exactly ``asyncio.CancelledError``; Shape B
    requires the message's *own last line* to name a ``CancelledError`` *and*
    the message to contain both of the specific frame names
    (``in lifespan``, ``in receive``) that identify this exact call chain. A
    genuine bug during shutdown -- a ``TypeError``, a broken ASGI lifespan
    hook, an actual crash, or even an unrelated ``CancelledError`` from
    somewhere else -- matches neither shape and is never touched. Every
    other uvicorn log record, on this logger or any other, is never touched
    either. Installed once per process (see
    :func:`_install_lifespan_cancellation_filter`), because the task it
    concerns is only ever cancelled well after the ``PeerServer.stop()``
    call that triggered it has already returned -- there is no narrower,
    still-correct window to scope this to. (Installing it before or after
    uvicorn's own ``Config.configure_logging()`` runs makes no difference --
    confirmed empirically: that call rebuilds *handlers* via
    ``logging.config.dictConfig``, and only for loggers whose dict entry
    names new ones; it never touches a logger's ``filters`` list.)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != _LIFESPAN_LOGGER_NAME:
            return True
        message = record.getMessage()

        if message.startswith(_LIFESPAN_ERROR_PREFIX):
            exc = record.exc_info[1] if record.exc_info else None
            return not isinstance(exc, asyncio.CancelledError)

        lines = message.rstrip().splitlines()
        if not lines:
            return True
        last_line = lines[-1]
        is_cancelled_error = any(
            last_line.startswith(prefix) for prefix in _CANCELLED_ERROR_LAST_LINE_PREFIXES
        )
        if not is_cancelled_error:
            return True
        is_this_call_chain = all(
            sig in message for sig in _LIFESPAN_CANCELLATION_FRAME_SIGNATURES
        )
        return not is_this_call_chain


_lifespan_cancellation_filter = _QuietExpectedLifespanCancellation()


def _install_lifespan_cancellation_filter() -> None:
    """Idempotent: safe to call once per ``PeerServer`` without stacking
    duplicate filters on the shared ``uvicorn.error`` logger."""
    logger = logging.getLogger(_LIFESPAN_LOGGER_NAME)
    if _lifespan_cancellation_filter not in logger.filters:
        logger.addFilter(_lifespan_cancellation_filter)
