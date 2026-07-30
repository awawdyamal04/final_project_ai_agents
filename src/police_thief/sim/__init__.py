"""Test-only local simulation.

**Nothing in this package is production authority.**

The real game has no component that sees both agents. This package deliberately
has one -- :class:`~police_thief.sim.harness.MatchHarness` -- so that Phase 1
can exercise the domain end-to-end before the network, commit-reveal and
capture-claim machinery exist to do the same job properly.

In the delivered system the harness's responsibilities are split across three
things that each have a *right* to their share of the information:

* turn coordination becomes the commit-reveal protocol (Phase 5);
* capture adjudication becomes the capture claim, where the cop claims and the
  thief is under a cryptographic obligation to answer truthfully (E-21, E-22);
* full reconstruction becomes the replay verifier, which runs only after the
  match (E-20).

The harness holds both positions, but never puts either inside the other peer's
:class:`~police_thief.domain.state.LocalState`. That separation is asserted by
``tests/domain/test_information_boundary.py``.
"""
