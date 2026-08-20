from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def learning_dir(tmp_path) -> Path:
    return tmp_path / "learning"
