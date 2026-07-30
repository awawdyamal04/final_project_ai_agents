"""Shared fixtures.

``valid_shared`` is loaded from the real ``config/game.json`` rather than an
inline literal, so the shipped configuration is exercised by every test that
mutates a copy of it. A shipped config that drifts out of compliance therefore
fails the suite instead of failing a match.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"
COP_EXAMPLE_PATH = REPO_ROOT / "config" / "cop.toml.example"
THIEF_EXAMPLE_PATH = REPO_ROOT / "config" / "thief.toml.example"


@pytest.fixture
def valid_shared() -> dict[str, Any]:
    """A fresh, mutable copy of the shipped shared configuration."""
    return json.loads(SHARED_CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def shared_path() -> Path:
    return SHARED_CONFIG_PATH


@pytest.fixture
def cop_example_path() -> Path:
    return COP_EXAMPLE_PATH


@pytest.fixture
def thief_example_path() -> Path:
    return THIEF_EXAMPLE_PATH


def deep_copy_with(
    mapping: dict[str, Any], section: str, key: str, value: Any
) -> dict[str, Any]:
    """Return a copy of ``mapping`` with one nested value replaced."""
    clone = copy.deepcopy(mapping)
    clone[section][key] = value
    return clone
