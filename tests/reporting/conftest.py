from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """``write_report`` targets a relative ``results/league`` -- keep test
    output out of the real repository tree."""
    monkeypatch.chdir(tmp_path)
