"""``--gui-delay``: CLI parsing and validation only.

Split out of ``peer/run.py`` (Q-19, D-44). Pure and standalone -- runs during
``argparse.parse_args``, i.e. before the peer, the orchestrator or any network
connection exists, so a bad value never gets the chance to affect a running
match.
"""

from __future__ import annotations

import argparse
import math

GUI_DELAY_MAX_SEC = 10.0
"""Upper bound for --gui-delay. A demo pacing knob, not a protocol value --
there is no Appendix F parameter here to violate, but an unbounded value would
let a typo hang a demo indefinitely, so it is rejected the same way a bad
config value is: before anything starts."""


def gui_delay_seconds(raw: str) -> float:
    """argparse ``type=`` for ``--gui-delay``: a finite value in [0, 10].

    Standalone and importable (not a closure) so it can be unit-tested without
    invoking the full CLI.
    """
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--gui-delay must be a number, got {raw!r}"
        ) from exc
    if math.isnan(value):
        raise argparse.ArgumentTypeError("--gui-delay must not be NaN")
    if math.isinf(value):
        raise argparse.ArgumentTypeError("--gui-delay must be finite")
    if value < 0:
        raise argparse.ArgumentTypeError("--gui-delay must not be negative")
    if value > GUI_DELAY_MAX_SEC:
        raise argparse.ArgumentTypeError(
            f"--gui-delay must be <= {GUI_DELAY_MAX_SEC}, got {value}"
        )
    return value
