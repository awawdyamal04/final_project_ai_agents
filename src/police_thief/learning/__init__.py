"""Persistent, cross-game adaptive learning (feat/adaptive-learning).

Hard boundary, stated once and enforced by ``tests/learning/test_boundary.py``:
nothing under this package may import ``police_thief.replay`` or
``police_thief.sim.harness`` -- the only two places global/omniscient truth
exists in this codebase (D-41, E-8/E-9). Every feature this package learns
from must already be legally visible to a live peer through its own
``LocalView``/``OpponentTracker`` (see ``strategy/base.py``,
``strategy/opponent_model.py``) or through this peer's own honest post-match
bookkeeping (``reporting/match_report.py``, its own audit-chain verification,
its own capture_claim verdicts). Nothing here ever reads an opponent's secret
nonce before its legal reveal, and nothing here ever holds both agents'
positions at once.

Learning never overwrites the shipped production strategy classes or their
default weights -- see ``adaptation.py``: it only proposes small, bounded
adjustments around those defaults, and ``promotion.py`` gates whether a
learned configuration is ever used as a new default at all.
"""
