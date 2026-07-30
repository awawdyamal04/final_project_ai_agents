"""The verification CLI: output, exit codes, determinism, and no secret leakage."""

from __future__ import annotations

import json

import pytest

from police_thief.config.verify import main


def test_valid_config_exits_zero_and_prints_the_hash(
    capsys, shared_path, cop_example_path
):
    code = main(["--shared", str(shared_path), "--private", str(cop_example_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "VALID    shared configuration" in out
    assert "VALID    private configuration" in out
    assert "role                 police" in out
    assert "32 validated" in out
    assert "14 fixed, 9 minimum, 9 negotiable" in out
    assert "config_sha256" in out


def test_output_is_deterministic_across_runs(capsys, shared_path):
    main(["--shared", str(shared_path)])
    first = capsys.readouterr().out
    main(["--shared", str(shared_path)])
    second = capsys.readouterr().out
    assert first == second


def test_detects_the_thief_role(capsys, shared_path, thief_example_path):
    code = main(["--shared", str(shared_path), "--private", str(thief_example_path)])
    assert code == 0
    assert "role                 thief" in capsys.readouterr().out


def test_expect_role_mismatch_fails(capsys, shared_path, thief_example_path):
    code = main(
        [
            "--shared", str(shared_path),
            "--private", str(thief_example_path),
            "--expect-role", "police",
        ]
    )
    assert code == 1
    assert "separate processes" in capsys.readouterr().err


def test_invalid_shared_config_exits_nonzero(capsys, tmp_path, valid_shared):
    valid_shared["board_and_agents"]["grid_size"] = 5
    path = tmp_path / "game.json"
    path.write_text(json.dumps(valid_shared), encoding="utf-8")

    code = main(["--shared", str(path)])
    err = capsys.readouterr().err
    assert code == 1
    assert "INVALID" in err
    assert "MinimumParameterViolationError" in err


def test_missing_file_exits_nonzero(capsys, tmp_path):
    code = main(["--shared", str(tmp_path / "absent.json")])
    assert code == 1
    assert "ConfigFileNotFoundError" in capsys.readouterr().err


def test_expect_hash_match_succeeds(capsys, shared_path):
    from police_thief.config.hashing import config_sha256
    from police_thief.config.loader import load_shared_config

    digest = config_sha256(load_shared_config(shared_path).raw)
    code = main(["--shared", str(shared_path), "--expect-hash", digest])
    assert code == 0
    assert "hash match           yes" in capsys.readouterr().out


def test_expect_hash_mismatch_refuses_to_play(capsys, shared_path):
    code = main(["--shared", str(shared_path), "--expect-hash", "0" * 64])
    assert code == 1
    assert "Refuse to play" in capsys.readouterr().err


def test_private_config_does_not_change_the_printed_hash(
    capsys, shared_path, cop_example_path, thief_example_path
):
    """The cop and thief run different private files; the hash must not move."""

    def digest_line(argv):
        main(argv)
        out = capsys.readouterr().out
        return next(l for l in out.splitlines() if "config_sha256" in l)

    alone = digest_line(["--shared", str(shared_path)])
    with_cop = digest_line(
        ["--shared", str(shared_path), "--private", str(cop_example_path)]
    )
    with_thief = digest_line(
        ["--shared", str(shared_path), "--private", str(thief_example_path)]
    )
    assert alone == with_cop == with_thief


def test_no_credential_contents_are_printed(
    capsys, shared_path, cop_example_path, tmp_path, monkeypatch
):
    """A credentials file next to the config must never be read or echoed."""
    secret = tmp_path / "credentials.json"
    secret.write_text('{"client_secret": "SUPER-SECRET-VALUE"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    main(["--shared", str(shared_path), "--private", str(cop_example_path)])
    captured = capsys.readouterr()
    assert "SUPER-SECRET-VALUE" not in captured.out
    assert "SUPER-SECRET-VALUE" not in captured.err
    assert "client_secret" not in captured.out
    # The path is shown so a misconfiguration is visible; the file is not read.
    assert "credentials.json (not read)" in captured.out
