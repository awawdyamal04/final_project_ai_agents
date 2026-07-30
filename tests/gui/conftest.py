"""GUI fixtures.

Reuses the peer fixtures, which live in a sibling package and are therefore not
inherited automatically.
"""

from __future__ import annotations

import pytest

from police_thief.config.loader import load_private_config, load_shared_config
from tests.conftest import (
    COP_EXAMPLE_PATH,
    SHARED_CONFIG_PATH,
    THIEF_EXAMPLE_PATH,
)


@pytest.fixture
def shared():
    return load_shared_config(SHARED_CONFIG_PATH)


@pytest.fixture
def cop_private():
    return load_private_config(COP_EXAMPLE_PATH)


@pytest.fixture
def thief_private():
    return load_private_config(THIEF_EXAMPLE_PATH)


@pytest.fixture
def peer_pair(shared, cop_private, thief_private):
    from tests.peer.conftest import build_peer

    cop = build_peer(shared, cop_private)
    thief = build_peer(shared, thief_private)
    cop.client.target = thief.server
    thief.client.target = cop.server
    return cop, thief
