"""Information boundary for the transport layer (E-8, E-9, E-39).

Phase 1 proved a peer's *state* cannot hold the opponent's position. This file
proves the same for everything the transport touches: no wire schema can carry
one, no orchestrator field holds one, and the FastMCP layer has no access to the
code that would need one.

Several of these are static import scans. That is deliberate: an import-graph
assertion fails the moment someone reaches for the wrong module, which is
earlier and louder than any runtime check.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from police_thief.domain.enums import Role
from police_thief.peer import client as client_module
from police_thief.peer import orchestrator as orchestrator_module
from police_thief.peer import server as server_module
from police_thief.peer.events import FORBIDDEN_EVENT_KEYS, MemoryEventSink
from police_thief.peer.orchestrator import HandshakeState, PeerOrchestrator
from police_thief.protocol import messages as messages_module
from police_thief.protocol.messages import MessageType, new_envelope
from tests.peer.conftest import build_peer

BANNED_POSITION_NAMES = (
    "opponent_position",
    "opponent_cell",
    "true_opponent_position",
    "thief_position",
    "cop_position",
    "global_state",
    "full_board_state",
    "board_state",
    "ground_truth",
)


def imported_modules(module) -> set[str]:
    """Every module named in an import statement of ``module``'s source."""
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# ----------------------------------------------------------------------
# Wire schemas
# ----------------------------------------------------------------------


def test_no_payload_schema_accepts_a_position():
    """Not one of the ten message types has a field for a position."""
    schemas = messages_module._PAYLOAD_SCHEMAS
    assert set(schemas) == set(MessageType)
    for message_type, schema in schemas.items():
        for key in schema:
            lowered = key.lower()
            assert "position" not in lowered, f"{message_type.value}.{key}"
            assert "cell" not in lowered, f"{message_type.value}.{key}"
            assert "board" not in lowered, f"{message_type.value}.{key}"


def test_envelope_has_no_position_field():
    assert not (messages_module.ENVELOPE_KEYS & set(BANNED_POSITION_NAMES))


@pytest.mark.parametrize("banned", BANNED_POSITION_NAMES)
def test_a_position_cannot_be_smuggled_into_any_payload(banned):
    """Closed payload schemas reject the field outright."""
    from police_thief.protocol.exceptions import ProtocolValidationError

    for message_type in MessageType:
        with pytest.raises(ProtocolValidationError, match="unknown payload field"):
            new_envelope(
                game_id="g1",
                sender_role=Role.POLICE,
                receiver_role=Role.THIEF,
                message_type=message_type,
                payload={banned: [3, 3]},
            )


@pytest.mark.asyncio
async def test_no_handshake_message_carries_game_information(peer_pair):
    """Every byte sent during the handshake, inspected."""
    cop, thief = peer_pair
    cop.orchestrator.mark_server_ready("http://a/mcp")
    await cop.orchestrator.wait_for_peer(attempts=1)
    await cop.orchestrator.perform_handshake()

    assert cop.client.sent
    for envelope in cop.client.sent:
        text = json.dumps(envelope.to_wire())
        for banned in BANNED_POSITION_NAMES:
            assert banned not in text
        # The thief starts at [3,3]; that pair must appear nowhere.
        assert "[3, 3]" not in text and "[3,3]" not in text


# ----------------------------------------------------------------------
# The orchestrator
# ----------------------------------------------------------------------


def test_orchestrator_has_no_global_state_field(peer_pair):
    cop, _ = peer_pair
    for banned in BANNED_POSITION_NAMES:
        assert not hasattr(cop.orchestrator, banned)


def test_orchestrator_holds_exactly_one_local_state(peer_pair):
    """Its own. There is no second one for the opponent."""
    cop, _ = peer_pair
    from police_thief.domain.state import LocalState

    states = [
        name
        for name, value in vars(cop.orchestrator).items()
        if isinstance(value, LocalState)
    ]
    assert states == ["state"]
    assert cop.orchestrator.state.role is cop.orchestrator.role


def test_handshake_state_carries_no_game_information():
    """The handshake establishes shared physics, not game state."""
    fields = {f.name for f in dataclasses.fields(HandshakeState)}
    for banned in BANNED_POSITION_NAMES:
        assert banned not in fields
    assert fields == {
        "opponent_name",
        "opponent_software_version",
        "opponent_capabilities",
        "opponent_config_sha256",
        "our_hello_acknowledged",
        "our_config_accepted",
        "opponent_ready",
        "we_sent_ready",
    }


@pytest.mark.asyncio
async def test_handshake_does_not_change_local_state(peer_pair):
    """A completed handshake must leave the game exactly where it started."""
    cop, thief = peer_pair
    before_cop = cop.orchestrator.state
    before_thief = thief.orchestrator.state

    cop.orchestrator.mark_server_ready("http://a/mcp")
    thief.orchestrator.mark_server_ready("http://b/mcp")
    await cop.orchestrator.wait_for_peer(attempts=1)
    await thief.orchestrator.wait_for_peer(attempts=1)
    await cop.orchestrator.perform_handshake()
    await thief.orchestrator.perform_handshake()

    assert cop.orchestrator.state == before_cop
    assert thief.orchestrator.state == before_thief
    assert cop.orchestrator.state.turn == 0


def test_status_exposes_no_opponent_information(peer_pair):
    cop, _ = peer_pair
    status = json.dumps(cop.orchestrator.status())
    for banned in BANNED_POSITION_NAMES:
        assert banned not in status


# ----------------------------------------------------------------------
# Static import boundaries
# ----------------------------------------------------------------------


def test_transport_layer_does_not_import_game_logic():
    """The FastMCP layer must not reach scoring, capture or strategy."""
    forbidden = {
        "police_thief.domain.scoring",
        "police_thief.domain.capture",
        "police_thief.domain.transition",
        "police_thief.domain.rules",
        "police_thief.domain.simultaneity",
        "police_thief.sim.harness",
    }
    for module in (server_module, client_module):
        leaked = imported_modules(module) & forbidden
        assert not leaked, f"{module.__name__} imports {sorted(leaked)}"


def test_server_never_calls_capture_functions():
    source = Path(server_module.__file__).read_text(encoding="utf-8")
    for name in (
        "evaluate_capture",
        "evaluate_barrier_capture",
        "evaluate_trapped_capture",
        "calculate_score",
    ):
        assert name not in source


def test_orchestrator_does_not_import_strategy_or_scoring():
    """It coordinates; it does not decide (Ch. 8, PDF p. 78)."""
    forbidden = {
        "police_thief.domain.scoring",
        "police_thief.domain.capture",
        "police_thief.sim.harness",
        "police_thief.sim.policies",
    }
    assert not (imported_modules(orchestrator_module) & forbidden)


def test_protocol_package_does_not_import_transport():
    """Describing a message must not require knowing how to send one."""
    from police_thief.protocol import action_codec, codec

    for module in (messages_module, codec, action_codec):
        assert not any(
            name.startswith("fastmcp") for name in imported_modules(module)
        )


# ----------------------------------------------------------------------
# Private configuration and secrets
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_private_configuration_is_never_transmitted(peer_pair):
    cop, thief = peer_pair
    cop.orchestrator.mark_server_ready("http://a/mcp")
    await cop.orchestrator.wait_for_peer(attempts=1)
    await cop.orchestrator.perform_handshake()

    private = cop.orchestrator.private
    for envelope in cop.client.sent:
        text = json.dumps(envelope.to_wire())
        assert str(private.email.credentials_path) not in text
        assert str(private.email.token_path) not in text
        assert private.email.recipient not in text
        assert private.network.opponent_url not in text
        assert str(private.network.port) not in text


@pytest.mark.asyncio
async def test_private_config_does_not_affect_the_config_hash(
    shared, cop_private, thief_private
):
    """The cop and thief run different private files against one constitution."""
    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    assert cop.orchestrator.private.role != thief.orchestrator.private.role
    assert cop.orchestrator.private.network.port != thief.orchestrator.private.network.port
    assert cop.orchestrator.config_hash == thief.orchestrator.config_hash


def test_event_sink_refuses_to_log_a_secret():
    sink = MemoryEventSink()
    with pytest.raises(ValueError, match="forbidden key"):
        sink.emit("outbound_message", client_secret="hunter2")


def test_event_sink_refuses_to_log_an_opponent_position():
    sink = MemoryEventSink()
    with pytest.raises(ValueError, match="forbidden key"):
        sink.emit("inbound_message", opponent_position=[3, 3])


def test_event_sink_checks_nested_structures():
    sink = MemoryEventSink()
    with pytest.raises(ValueError, match="forbidden key"):
        sink.emit("x", detail={"inner": [{"refresh_token": "abc"}]})


def test_forbidden_event_keys_cover_both_families():
    assert "refresh_token" in FORBIDDEN_EVENT_KEYS  # secrets (E-39)
    assert "opponent_position" in FORBIDDEN_EVENT_KEYS  # local truth (E-9)


@pytest.mark.asyncio
async def test_operational_log_of_a_full_handshake_is_clean(peer_pair):
    cop, thief = peer_pair
    cop.orchestrator.mark_server_ready("http://a/mcp")
    await cop.orchestrator.wait_for_peer(attempts=1)
    await cop.orchestrator.perform_handshake()

    text = json.dumps(cop.events.records)
    for banned in BANNED_POSITION_NAMES:
        assert banned not in text
    for secret in ("client_secret", "refresh_token", "credentials.json"):
        assert secret not in text


# ----------------------------------------------------------------------
# No central referee
# ----------------------------------------------------------------------


def test_no_module_holds_both_peers_states():
    """Outside the test-only sim package, nothing *holds* both sides.

    The check is for stored attributes (``self.cop_state = ...``), not for
    function parameters. Taking both positions as explicit arguments is the
    documented design (DECISIONS.md D-28): capture needs both, so it is a free
    function an adjudicator calls, precisely so that no live object has to hold
    them. Flagging a parameter would flag the thing that keeps the boundary.
    """
    src = Path(orchestrator_module.__file__).parents[2] / "police_thief"
    offenders: list[str] = []

    for path in sorted(src.rglob("*.py")):
        if "sim" in path.parts:
            continue  # documented test-only infrastructure
        tree = ast.parse(path.read_text(encoding="utf-8"))
        held: set[str] = set()
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    held.add(target.attr)
        for marker in ("cop_state", "thief_state", "both_states", "world_state"):
            if marker in held:
                offenders.append(f"{path.name}: self.{marker}")

    assert not offenders, f"a module holds both peers' states: {offenders}"


def test_capture_takes_positions_as_parameters_not_stored_state():
    """The counterpart to the test above: confirm the design it allows for."""
    from police_thief.domain import capture as capture_module

    params = set(
        inspect.signature(capture_module.evaluate_trapped_capture).parameters
    )
    assert "thief_state" in params  # a parameter...
    assert not hasattr(capture_module, "thief_state")  # ...not module state


def test_orchestrator_signature_takes_no_opponent_state():
    params = set(inspect.signature(PeerOrchestrator).parameters)
    for banned in ("opponent_state", "opponent", "world", "referee"):
        assert banned not in params
