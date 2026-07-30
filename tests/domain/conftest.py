"""Domain fixtures."""

from __future__ import annotations

import pytest

from police_thief.config.loader import load_shared_config
from police_thief.config.models import SharedConfig
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.enums import Role
from police_thief.domain.state import LocalState
from tests.conftest import SHARED_CONFIG_PATH


@pytest.fixture
def shared_config() -> SharedConfig:
    return load_shared_config(SHARED_CONFIG_PATH)


@pytest.fixture
def cop_state(shared_config) -> LocalState:
    return LocalState.initial(Role.POLICE, shared_config)


@pytest.fixture
def thief_state(shared_config) -> LocalState:
    return LocalState.initial(Role.THIEF, shared_config)


def place_at(state: LocalState, row: int, col: int) -> LocalState:
    """Move a state's agent to a specific cell, for constructing scenarios."""
    return state.with_position(Coordinate(row, col))


def wall_in(state: LocalState, cells: list[tuple[int, int]]) -> LocalState:
    """Add barriers directly, bypassing placement rules, to build a scenario."""
    board = state.board
    for row, col in cells:
        board = board.with_barrier(Coordinate(row, col))
    return state.with_board(board)
