"""CLI: validate configuration and print the shared hash.

    python -m police_thief.config.verify \\
        --shared config/game.json \\
        --private config/cop.toml.example

Exit codes: 0 valid, 1 invalid, 2 usage error.

Deliberately prints no secret material. The private file is summarised by role,
group, port and provider; credential *paths* are shown so a misconfiguration is
visible, but the files they point at are never opened or echoed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from police_thief.config.exceptions import ConfigError
from police_thief.config.hashing import config_sha256
from police_thief.config.loader import load_private_config, load_shared_config
from police_thief.config.policy import (
    BINDING_PARAMETER_COUNT,
    PARAMETER_POLICIES,
)
from police_thief.config.validation import validate_role_matches
from police_thief.domain.enums import ParameterStatus, Role


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m police_thief.config.verify",
        description=(
            "Validate the shared constitution and an optional private "
            "per-peer configuration, and print config_sha256."
        ),
    )
    parser.add_argument(
        "--shared",
        default="config/game.json",
        help="path to the shared configuration (default: config/game.json)",
    )
    parser.add_argument(
        "--private",
        default=None,
        help="path to a private per-peer TOML file (optional)",
    )
    parser.add_argument(
        "--expect-role",
        choices=[r.value for r in Role],
        default=None,
        help="assert the private configuration declares this role",
    )
    parser.add_argument(
        "--expect-hash",
        default=None,
        help="assert config_sha256 equals this digest (the opponent's)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    out = sys.stdout

    try:
        shared = load_shared_config(args.shared)
    except ConfigError as exc:
        print(f"INVALID  shared configuration: {args.shared}", file=sys.stderr)
        print(f"  {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    digest = config_sha256(shared.raw)

    fixed = sum(1 for p in PARAMETER_POLICIES if p.status is ParameterStatus.FIXED)
    minimum = sum(
        1 for p in PARAMETER_POLICIES if p.status is ParameterStatus.MINIMUM
    )
    negotiable = sum(
        1 for p in PARAMETER_POLICIES if p.status is ParameterStatus.NEGOTIABLE
    )

    print("VALID    shared configuration", file=out)
    print(f"  file                 {Path(args.shared)}", file=out)
    print(f"  schema_version       {shared.schema_version}", file=out)
    print(f"  agreed_between       {', '.join(shared.agreed_between)}", file=out)
    print(f"  board                {shared.grid_size}x{shared.grid_size}", file=out)
    print(
        f"  sub-games per match  {shared.network_and_league.num_games}", file=out
    )
    print(
        f"  binding parameters   {BINDING_PARAMETER_COUNT} validated "
        f"({fixed} fixed, {minimum} minimum, {negotiable} negotiable)",
        file=out,
    )
    print(f"  config_sha256        {digest}", file=out)

    if args.expect_hash is not None:
        if digest != args.expect_hash.strip().lower():
            print(
                f"MISMATCH config_sha256 differs from the expected digest\n"
                f"  computed {digest}\n  expected {args.expect_hash}\n"
                f"  Refuse to play: the two peers do not share the same "
                f"physics (E-11).",
                file=sys.stderr,
            )
            return 1
        print("  hash match           yes", file=out)

    if args.private is not None:
        try:
            private = load_private_config(args.private)
            if args.expect_role is not None:
                validate_role_matches(private.role, Role(args.expect_role))
        except ConfigError as exc:
            print(
                f"INVALID  private configuration: {args.private}", file=sys.stderr
            )
            print(f"  {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        print("VALID    private configuration", file=out)
        print(f"  file                 {Path(args.private)}", file=out)
        print(f"  role                 {private.role.value}", file=out)
        print(f"  group                {private.game.group_name} "
              f"({private.game.group_id})", file=out)
        print(f"  listen               {private.network.host}:"
              f"{private.network.port}", file=out)
        print(f"  verbal provider      {private.trash_talk.provider.value}", file=out)
        print(f"  email mode           {private.email.mode.value}", file=out)
        # Paths only -- never the contents of a credential file.
        print(f"  credentials path     {private.email.credentials_path} "
              f"(not read)", file=out)
        print("  private config does not affect config_sha256", file=out)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
