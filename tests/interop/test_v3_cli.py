"""Reference-v3 adapter -- Phase 9 CLI integration: ``--interop
reference-v3`` coexists with every native flag, with no breaking change to
the existing CLI surface.
"""

from __future__ import annotations

from police_thief.peer.run import _build_parser


def test_interop_flag_defaults_to_off():
    args = _build_parser().parse_args(["--private", "config/cop.toml.example"])
    assert args.interop is None
    assert args.interop_peer is None
    assert args.interop_role is None


def test_interop_flag_accepts_reference_v3():
    args = _build_parser().parse_args(
        ["--private", "config/cop.toml.example", "--interop", "reference-v3"]
    )
    assert args.interop == "reference-v3"


def test_interop_peer_and_role_are_independently_settable():
    args = _build_parser().parse_args([
        "--private", "config/cop.toml.example",
        "--interop", "reference-v3",
        "--interop-peer", "http://127.0.0.1:8931/mcp",
        "--interop-role", "thief",
    ])
    assert args.interop_peer == "http://127.0.0.1:8931/mcp"
    assert args.interop_role == "thief"


def test_every_existing_native_flag_is_still_present():
    """Additive-only: none of the flags Phase 9 predates were removed or
    renamed by this change."""
    args = _build_parser().parse_args(["--private", "config/cop.toml.example"])
    for flag in ("shared", "private", "game_id", "log_dir", "hold", "turns",
                 "opponent_url", "gui", "adaptive_learning", "learning_dir"):
        assert hasattr(args, flag)
