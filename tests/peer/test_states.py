"""The peer state machine (E-4, E-5)."""

from __future__ import annotations

import itertools

import pytest

from police_thief.peer.clock import FakeClock
from police_thief.peer.states import (
    TERMINAL_STATES,
    TRANSITIONS,
    PeerState,
    PeerStateMachine,
)
from police_thief.protocol.exceptions import InvalidPeerStateError


def machine(clock: FakeClock | None = None) -> PeerStateMachine:
    clock = clock or FakeClock()
    return PeerStateMachine(now=clock.monotonic)


def test_starts_in_created():
    assert machine().state is PeerState.CREATED


def test_every_state_has_a_transition_entry():
    assert set(TRANSITIONS) == set(PeerState)


def test_terminal_states_have_no_outgoing_transitions():
    for state in TERMINAL_STATES:
        assert TRANSITIONS[state] == frozenset()


@pytest.mark.parametrize(
    ("source", "target"),
    [(s, t) for s, targets in TRANSITIONS.items() for t in targets],
)
def test_every_declared_transition_is_accepted(source, target):
    m = machine()
    object.__setattr__(m, "_state", source)
    assert m.transition(target, "test").target is target
    assert m.state is target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (s, t)
        for s, t in itertools.product(PeerState, PeerState)
        if t not in TRANSITIONS[s] and s is not t
    ],
)
def test_every_undeclared_transition_is_rejected(source, target):
    m = machine()
    object.__setattr__(m, "_state", source)
    with pytest.raises(InvalidPeerStateError, match="illegal transition"):
        m.transition(target)
    assert m.state is source, "a rejected transition must not change state"


def test_rejected_transition_leaves_history_untouched():
    m = machine()
    m.transition(PeerState.STARTING)
    before = m.history
    with pytest.raises(InvalidPeerStateError):
        m.transition(PeerState.READY)
    assert m.history == before


def test_the_happy_path_runs_end_to_end():
    m = machine()
    path = [
        PeerState.STARTING,
        PeerState.SERVER_READY,
        PeerState.CONNECTING,
        PeerState.HELLO_EXCHANGE,
        PeerState.CONFIG_EXCHANGE,
        PeerState.CONFIG_VERIFIED,
        PeerState.READY_WAIT,
        PeerState.READY,
        PeerState.FINISHING,
        PeerState.FINISHED,
    ]
    for state in path:
        m.transition(state, "handshake")
    assert m.state is PeerState.FINISHED
    assert m.is_terminal
    assert [t.target for t in m.history] == path


def test_terminal_state_is_immutable():
    m = machine()
    m.transition(PeerState.STARTING)
    m.transition(PeerState.ERROR, "boom")
    assert m.is_terminal
    for target in PeerState:
        if target is PeerState.ERROR:
            continue
        with pytest.raises(InvalidPeerStateError):
            m.transition(target)


def test_repeating_a_transition_is_idempotent_and_does_not_duplicate_history():
    m = machine()
    m.transition(PeerState.STARTING, "first")
    length = len(m.history)
    record = m.transition(PeerState.STARTING, "again")
    assert record.reason == "idempotent"
    assert len(m.history) == length
    assert m.state is PeerState.STARTING


def test_re_entering_a_terminal_state_still_raises():
    """Idempotence must not become a way to keep acting after the end."""
    m = machine()
    m.transition(PeerState.STARTING)
    m.transition(PeerState.ERROR)
    with pytest.raises(InvalidPeerStateError):
        m.transition(PeerState.ERROR)


def test_disconnected_is_not_terminal_and_allows_wind_down():
    """A lost peer still needs a controlled exit (Ch. 8, PDF p. 79)."""
    assert PeerState.DISCONNECTED not in TERMINAL_STATES
    m = machine()
    for state in (
        PeerState.STARTING,
        PeerState.SERVER_READY,
        PeerState.CONNECTING,
        PeerState.DISCONNECTED,
        PeerState.FINISHING,
        PeerState.FINISHED,
    ):
        m.transition(state)
    assert m.state is PeerState.FINISHED


def test_transition_log_is_deterministic_and_timestamped():
    clock = FakeClock()
    m = machine(clock)
    m.transition(PeerState.STARTING, "a")
    clock.advance(2.5)
    m.transition(PeerState.SERVER_READY, "b")

    log = [t.to_dict() for t in m.history]
    assert log == [
        {"from": "created", "to": "starting", "reason": "a", "at": 0.0},
        {"from": "starting", "to": "server_ready", "reason": "b", "at": 2.5},
    ]


def test_require_accepts_and_rejects():
    m = machine()
    m.require(PeerState.CREATED)
    with pytest.raises(InvalidPeerStateError, match="requires one of"):
        m.require(PeerState.READY)


def test_state_cannot_be_assigned_from_outside():
    """No direct assignment: the property is read-only."""
    m = machine()
    with pytest.raises(AttributeError):
        m.state = PeerState.READY  # type: ignore[misc]
