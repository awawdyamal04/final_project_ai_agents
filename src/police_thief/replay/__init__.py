"""Independent two-log replay verification.

Reconstructs a whole sub-game from the two peers' audit logs and decides the
result **without trusting either peer's account of it**. Every claim is checked
against the other side's record and against the agreed physics; a claimed score
is compared, never adopted.

This is the only omniscient component in the project, and it is allowed to be:
it runs offline, after the final reveal, when the nonces are already public
(E-18). It shares no code path with the live peer -- see
``tests/replay/test_two_log_replay.py``, which asserts the live peer never
imports it.
"""

from police_thief.replay.verifier import (
    ReplayVerdict,
    Verdict,
    replay_files,
    replay_logs,
)

__all__ = ["ReplayVerdict", "Verdict", "replay_files", "replay_logs"]
