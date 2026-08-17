"""``--gui-delay``: CLI validation, rejected before the peer ever starts.

Split out of ``test_run_cli.py`` (150-line compliance pass, D-44). argparse
raises during ``parse_args``, which runs before any config load, socket or
orchestrator exists.
"""

from __future__ import annotations

import argparse

import pytest

from police_thief.peer.gui_cli import GUI_DELAY_MAX_SEC, gui_delay_seconds
from police_thief.peer.run import _build_parser


def test_gui_delay_default_is_zero():
    args = _build_parser().parse_args(["--private", "config/cop.toml.example"])
    assert args.gui_delay == 0.0


@pytest.mark.parametrize(
    "raw,expected",
    [("0", 0.0), ("1", 1.0), ("1.5", 1.5), ("10", 10.0), ("10.0", 10.0)],
)
def test_gui_delay_accepts_valid_values(raw, expected):
    args = _build_parser().parse_args(
        ["--private", "config/cop.toml.example", "--gui-delay", raw]
    )
    assert args.gui_delay == expected


@pytest.mark.parametrize(
    "raw",
    ["-1", "-0.01", "nan", "NaN", "inf", "-inf", "Infinity", "11", "10.01", "999", "abc", ""],
)
def test_gui_delay_rejects_invalid_values_at_parse_time(raw):
    """Negative, NaN, infinite, excessive and non-numeric values all fail
    during argument parsing -- i.e. before ``main()`` does anything else."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(
            ["--private", "config/cop.toml.example", "--gui-delay", raw]
        )


def test_gui_delay_seconds_helper_rejects_nan_directly():
    with pytest.raises(argparse.ArgumentTypeError, match="NaN"):
        gui_delay_seconds("nan")


def test_gui_delay_seconds_helper_rejects_infinity_directly():
    with pytest.raises(argparse.ArgumentTypeError, match="finite"):
        gui_delay_seconds("inf")
    with pytest.raises(argparse.ArgumentTypeError, match="finite"):
        gui_delay_seconds("-inf")


def test_gui_delay_seconds_helper_rejects_negative_directly():
    with pytest.raises(argparse.ArgumentTypeError, match="negative"):
        gui_delay_seconds("-0.5")


def test_gui_delay_seconds_helper_accepts_the_boundary_values():
    assert gui_delay_seconds("0") == 0.0
    assert gui_delay_seconds(str(GUI_DELAY_MAX_SEC)) == GUI_DELAY_MAX_SEC


def test_gui_delay_seconds_helper_rejects_just_over_the_maximum():
    with pytest.raises(argparse.ArgumentTypeError, match=r"<="):
        gui_delay_seconds(str(GUI_DELAY_MAX_SEC + 0.01))


def test_gui_delay_seconds_helper_rejects_non_numeric_text():
    with pytest.raises(argparse.ArgumentTypeError, match="number"):
        gui_delay_seconds("soon")
